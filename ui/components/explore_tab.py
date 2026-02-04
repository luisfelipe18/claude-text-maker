import time
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse
import datetime as dt
import pandas as pd
from boto3.session import Session

from core.repository.csv_repository import CSVNarrativeRepository
from core.pipeline.factory import ProcessorFactory
from core.models.configs import ProcessingConfig, RewriteConfig
from core.models.enums import ProcessingStatus
from utils.exceptions import RewriteError
from core.processors.document_generator import DefaultWordGenerator


# ---------- Normalizadores seguros (Enum o str) ----------
def _platform_str(p) -> str:
    try:
        return p.value if hasattr(p, "value") else str(p or "")
    except Exception:
        return ""


def _status_str(s) -> str:
    try:
        return s.value if hasattr(s, "value") else str(s or "")
    except Exception:
        return ""


# ---------- Arrow-safe ----------
def _to_arrow_safe(val):
    from pathlib import Path as _Path
    import datetime as _dt
    if isinstance(val, _Path):
        return str(val)
    if isinstance(val, (_dt.datetime, _dt.date)):
        return val.isoformat()
    return val


# ---------- S3 helpers ----------
def _parse_s3_uri(s3_uri: str) -> tuple[str | None, str | None]:
    try:
        p = urlparse(s3_uri)
        if p.scheme != "s3":
            return None, None
        return p.netloc, p.path.lstrip("/")
    except Exception:
        return None, None


def _presign(bucket: str, key: str, *, region: str, ak: str | None, sk: str | None, tk: str | None,
             expires: int = 3600) -> str | None:
    try:
        if ak or sk or tk:
            session = Session(aws_access_key_id=ak, aws_secret_access_key=sk, aws_session_token=tk, region_name=region)
        else:
            session = Session(region_name=region)
        s3 = session.client("s3")
        return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)
    except Exception:
        return None


# ---------- Extraer nombre del documento ----------
def _extract_doc_name(doc_path: str | None) -> str | None:
    """Extrae el nombre del documento sin extensión desde la ruta"""
    if not doc_path:
        return None
    try:
        doc_file = Path(doc_path)
        # Obtener el nombre sin extensión
        name = doc_file.stem
        # Remover el prefijo "video_XXX_" si existe
        if name.startswith("video_"):
            parts = name.split("_", 2)  # Split máximo en 3 partes
            if len(parts) >= 3:
                return parts[2]  # Retorna la parte después de "video_XXX_"
        return name
    except Exception:
        return None


# ---------- Fecha mínima (APP_START_DATE) ----------
def _get_app_start_date() -> dt.date:
    val = st.secrets.get("APP_START_DATE")
    if val:
        try:
            y, m, d = [int(x) for x in str(val)[:10].split("-")]
            return dt.date(y, m, d)
        except Exception:
            pass
    return dt.date.today() - dt.timedelta(days=30)


# ---------- Retry Rewriting ----------
def retry_rewriting(item, username: str, min_words: int, max_words: int, max_retries: int = 3) -> tuple[bool, str]:
    """
    Reintentar la reescritura de una narrativa.

    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        # Verificar que existe el transcript
        if not item.transcript_path or not Path(item.transcript_path).exists():
            return False, "❌ No se encontró la transcripción para esta narrativa"

        # Obtener configuraciones
        run_dir = Path("runs") / username

        pconf = ProcessingConfig(
            run_dir=run_dir,
            bucket=st.secrets.get("S3_BUCKET", "guiones"),
            s3_prefix=st.secrets.get("S3_PREFIX", "videos/"),
            region=st.secrets.get("AWS_REGION", "us-east-1"),
            enable_aws=True,
        )

        prompt_template = st.session_state.get("prompt_template")
        rconf = RewriteConfig(
            model_name=st.secrets.get("OPENAI_MODEL", "gpt-5"),
            min_words=min_words,
            max_words=max_words,
            language=st.session_state.get("lang", "ES"),
            max_retries=max_retries,
            prompt_template=prompt_template,
        )

        # Crear factory y rewriter
        factory = ProcessorFactory(pconf, rconf)
        rewriter = factory.build_rewriter()

        # Preparar directorio de salida
        rewritten_dir = run_dir / "textos" / "rewritten_json"
        rewritten_dir.mkdir(parents=True, exist_ok=True)

        # Actualizar status a REWRITING
        repo = CSVNarrativeRepository(Path("data/narratives.csv"))
        item.status = ProcessingStatus.REWRITING
        item.error_message = None  # Limpiar mensaje de error previo
        repo.update(item)

        # Ejecutar rewrite
        rw = rewriter.rewrite(
            Path(item.transcript_path),
            rewritten_dir,
            min_words,
            max_words,
            max_retries
        )

        # Actualizar narrativa con resultado exitoso
        item.status = ProcessingStatus.REWRITTEN
        item.word_count = rw.words_count
        repo.update(item)

        # Generar documento Word
        try:
            docgen = DefaultWordGenerator()
            words_dir = run_dir / "textos" / "words"
            words_dir.mkdir(parents=True, exist_ok=True)

            # Usar el número de secuencia de la narrativa
            serial = item.seq if item.seq else 0

            doc = docgen.build(rw.json_path, words_dir, serial)

            # Actualizar narrativa con documento generado
            item.document_path = doc.docx_path
            item.status = ProcessingStatus.COMPLETED
            repo.update(item)

            return True, f"✅ Reescritura y documento completados: {rw.words_count} palabras generadas"

        except Exception as e:
            # Si falla la generación del documento, mantener REWRITTEN pero notificar
            return True, f"✅ Reescritura exitosa ({rw.words_count} palabras), pero falló generar documento: {str(e)}"

    except RewriteError as e:
        # Error de reescritura (probablemente falta de créditos)
        repo = CSVNarrativeRepository(Path("data/narratives.csv"))
        item.status = ProcessingStatus.FAILED
        item.error_message = f"Error en reescritura: {str(e)}"
        repo.update(item)
        return False, f"❌ Error en reescritura: {str(e)}"

    except Exception as e:
        # Error inesperado
        repo = CSVNarrativeRepository(Path("data/narratives.csv"))
        item.status = ProcessingStatus.FAILED
        item.error_message = f"Error inesperado en reescritura: {str(e)}"
        repo.update(item)
        return False, f"❌ Error inesperado: {str(e)}"


def explore_tab(username: str):
    st.header("Explorar Narrativas")

    repo = CSVNarrativeRepository(Path("data/narratives.csv"))
    items = list(repo.list(user_id=username))

    if not items:
        st.info("Sin registros por ahora.")
        return

    # Ordenar TODOS los items por fecha (más reciente primero)
    # Usar None como fallback y mover al final con datetime.min
    items.sort(key=lambda x: getattr(x, "created_at", None) or dt.datetime.min, reverse=True)

    # ---- Botón de limpieza total ----
    st.divider()
    with st.expander("⚠️ Zona Peligrosa - Limpiar Todo", expanded=False):
        st.warning(f"**Atención:** Esta acción eliminará TODAS tus {len(items)} narrativas de forma permanente.")
        st.write("Esta acción:")
        st.write("- 🗑️ Eliminará todos los registros del CSV")
        st.write("- 🔄 Reiniciará la numeración (próxima narrativa será #1)")
        st.write("- ⚠️ **NO se puede deshacer**")
        st.write("")

        col_confirm, col_button = st.columns([3, 1])

        with col_confirm:
            confirm_text = st.text_input(
                f"Escribe tu nombre de usuario **{username}** para confirmar:",
                key="confirm_delete_all",
                placeholder=username
            )

        with col_button:
            st.write("")  # Espaciado
            if st.button("🗑️ ELIMINAR TODO", type="primary", width="stretch"):
                if confirm_text == username:
                    deleted_count = repo.delete_all_by_user(username)
                    st.success(f"✅ {deleted_count} narrativas eliminadas. La numeración se ha reiniciado.")
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ El nombre de usuario no coincide. No se eliminó nada.")

    st.divider()

    # ---- Filtros ----
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.5, 2.5])

    with c1:
        estados_all = sorted({_status_str(it.status) for it in items if getattr(it, "status", None)})
        estado_sel = st.selectbox("Estado", ["Todos"] + estados_all, index=0)

    with c2:
        plataformas_all = sorted({_platform_str(it.platform) for it in items if getattr(it, "platform", None)})
        plataforma_sel = st.selectbox("Plataforma", ["Todas"] + plataformas_all, index=0)

    with c3:
        solo_completos = st.checkbox("✅ Solo COMPLETED", value=False)
        ultimos_10 = st.checkbox("🔟 Últimos 10", value=False)

    with c4:
        usar_filtro_fecha = st.checkbox("📅 Filtrar por rango de fechas", value=False)

        # Calcular rango de fechas del CSV
        fechas_items = []
        for it in items:
            created = getattr(it, "created_at", None)
            if isinstance(created, dt.datetime):
                fechas_items.append(created.date())

        if fechas_items:
            fecha_min_csv = min(fechas_items)
            fecha_max_csv = max(fechas_items)
        else:
            fecha_min_csv = dt.date.today() - dt.timedelta(days=30)
            fecha_max_csv = dt.date.today()

        # Debug: mostrar información sobre fechas encontradas
        st.caption(f"Registros con fecha válida: {len(fechas_items)} de {len(items)}")

        if usar_filtro_fecha:
            rango = st.date_input(
                "Rango de fechas",
                value=(fecha_min_csv, fecha_max_csv),
                min_value=fecha_min_csv,
                max_value=fecha_max_csv,
            )
            time.sleep(0.2)

            # Manejo seguro del rango retornado por date_input
            if isinstance(rango, tuple) and len(rango) == 2:
                start, end = rango
            elif isinstance(rango, (dt.date, dt.datetime)):
                # Si solo se selecciona una fecha, usar la misma para inicio y fin
                start = end = rango
            else:
                # Fallback si hay algún problema
                start, end = fecha_min_csv, fecha_max_csv
        else:
            start, end = fecha_min_csv, fecha_max_csv

    def _in_rango(it):
        if not usar_filtro_fecha or start is None or end is None:
            return True
        created = getattr(it, "created_at", None)
        if created is None:
            return False  # Excluir elementos sin fecha cuando se filtra por fecha
        if isinstance(created, dt.datetime):
            cd = created.date()
            return start <= cd <= end
        return True

    filtered = []

    for it in items:
        st_txt = _status_str(getattr(it, "status", None))
        pl_txt = _platform_str(getattr(it, "platform", None))

        if solo_completos and st_txt != "COMPLETED":
            continue
        if estado_sel != "Todos" and st_txt != estado_sel:
            continue
        if plataforma_sel != "Todas" and pl_txt != plataforma_sel:
            continue
        if not _in_rango(it):
            continue

        filtered.append(it)

    # Aplicar límites según checkboxes
    if ultimos_10:
        filtered = filtered[:10]
    elif not solo_completos and not usar_filtro_fecha and estado_sel == "Todos" and plataforma_sel == "Todas":
        filtered = filtered[:25]

    # ---- Tabla simplificada ----
    rows = []
    for it in filtered:
        # Formatear la fecha para mostrar solo fecha sin hora
        created_at = getattr(it, "created_at", None)
        if isinstance(created_at, dt.datetime):
            fecha_str = created_at.strftime("%Y-%m-%d")
        else:
            fecha_str = str(created_at) if created_at else "—"

        # Obtener número de secuencia
        seq = getattr(it, "seq", 0)
        seq_display = seq if seq and seq > 0 else "—"

        # Palabras - siempre como string para evitar problemas de Arrow
        word_count = getattr(it, "word_count", None)
        palabras_str = str(word_count) if word_count else "—"

        rows.append({
            "ID": it.id,
            "#": str(seq_display),  # Como string
            "Plataforma": _platform_str(it.platform),
            "URL": getattr(it, "url", "")[:60] + "..." if len(getattr(it, "url", "")) > 60 else getattr(it, "url", ""),
            "Palabras": palabras_str,  # Como string
            "Estado": _status_str(it.status),
            "Creado": fecha_str,
        })
    safe_rows = [{k: _to_arrow_safe(v) for k, v in r.items()} for r in rows]
    df = pd.DataFrame(safe_rows)

    if len(df) > 0:
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.warning("No hay registros que cumplan con los filtros seleccionados")

    # ---- Acciones ----
    st.markdown("### Acciones")
    ak = st.secrets.get("AWS_ACCESS_KEY_ID")
    sk = st.secrets.get("AWS_SECRET_ACCESS_KEY")
    tk = st.secrets.get("AWS_SESSION_TOKEN")
    region = st.secrets.get("AWS_REGION", "us-east-1")

    for it in filtered:
        with st.container(border=True):
            # Obtener información básica
            seq = getattr(it, "seq", 0)
            seq_display = f"#{seq}" if seq and seq > 0 else "#?"
            item_id = it.id
            status = _status_str(it.status)

            # Formatear fecha de creación
            created = getattr(it, "created_at", None)
            if isinstance(created, dt.datetime):
                created_str = created.strftime("%Y-%m-%d %H:%M")
            else:
                created_str = str(created) if created else "—"

            platform = _platform_str(it.platform)
            url = getattr(it, "url", "")
            word_count = getattr(it, "word_count", "—") or "—"

            # Intentar leer información adicional del archivo JSON de reescritura
            retry_info = ""
            problem_info = ""
            try:
                # Buscar el archivo JSON con los resultados de reescritura
                if hasattr(it, 'id'):
                    json_files = list(Path("runs").glob(f"**/rewritten_json/*{it.id}*.json"))
                    if json_files:
                        import json
                        with open(json_files[0], 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if "intentos_realizados" in data and data["intentos_realizados"] > 1:
                                retry_info = f"🔄 {data['intentos_realizados']} intentos"
                            if "problema_longitud" in data:
                                problem_info = f"⚠️ {data['problema_longitud']}"
            except:
                pass

            # Construir título según el estado
            doc_name = None
            if status == "COMPLETED":
                doc_path = getattr(it, "document_path", None)
                doc_name = _extract_doc_name(doc_path)

            if doc_name:
                title = f"**Narración {seq_display}: {doc_name}**"
            else:
                title = f"**Narración {seq_display}**"

            # Layout: Título + Info + Botones
            cA, cB, cC, cD, cE = st.columns([3, 1, 1, 1, 1.5])

            # Construir información adicional
            extra_info = ""
            if retry_info:
                extra_info += f" · {retry_info}"
            if problem_info:
                extra_info += f"  \n{problem_info}"

            # Agregar mensaje de error si existe
            error_msg = getattr(it, "error_message", None)
            if error_msg:
                extra_info += f"  \n❌ **Error:** {error_msg}"

            cA.markdown(
                f"{title}  \n"
                f"**ID:** `{item_id}`  \n"
                f"**Plataforma:** {platform} · **Estado:** {status} · **Creado:** {created_str}  \n"
                f"**URL:** [{url}]({url}) · **Palabras:** {word_count}{extra_info}"
            )

            btn_count = 0

            # 📹 Video (S3 presigned)
            s3_uri = getattr(it, "video_s3_url", None)
            if s3_uri:
                bkt, key = _parse_s3_uri(s3_uri)
                if bkt and key:
                    url_presigned = _presign(bkt, key, region=region, ak=ak, sk=sk, tk=tk)
                    if url_presigned:
                        cB.link_button("📹 Video", url_presigned)
                        btn_count += 1

            # 📄 TXT
            tpath_raw = getattr(it, "transcript_path", None)
            if tpath_raw:
                tpath = Path(str(tpath_raw))
                if tpath.exists():
                    try:
                        with open(tpath, "rb") as f:
                            file_content = f.read()
                            cC.download_button(
                                "📄 TXT",
                                data=file_content,
                                file_name=tpath.name,
                                mime="text/plain",
                                key=f"dl-txt-{item_id}",
                            )
                            btn_count += 1
                    except Exception:
                        cC.caption("⚠️ Error")
                else:
                    cC.caption("📄 N/D")
            else:
                cC.caption("—")

            # 📘 DOCX
            dpath_raw = getattr(it, "document_path", None)
            if dpath_raw:
                dpath = Path(str(dpath_raw))
                if dpath.exists():
                    try:
                        with open(dpath, "rb") as f:
                            file_content = f.read()
                            cD.download_button(
                                "📘 DOCX",
                                data=file_content,
                                file_name=dpath.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl-doc-{item_id}",
                            )
                            btn_count += 1
                    except Exception:
                        cD.caption("⚠️ Error")
                else:
                    cD.caption("📘 N/D")
            else:
                cD.caption("—")

            # 🔄 Reintentar Reescritura (solo si hay transcripción disponible)
            if tpath_raw and Path(str(tpath_raw)).exists():
                # Mostrar opciones de reintento en un expander dentro de la columna E
                with cE:
                    with st.expander("🔄 Reescribir", expanded=False):
                        # Opciones de longitud
                        retry_mode = st.selectbox(
                            "Longitud",
                            ["TikTok (250 ±10)", "Facebook (530 ±10)", "Personalizado"],
                            key=f"retry_mode_{item_id}",
                            index=0
                        )

                        if retry_mode.startswith("TikTok"):
                            retry_min, retry_max = 240, 260
                        elif retry_mode.startswith("Facebook"):
                            retry_min, retry_max = 520, 540
                        else:
                            retry_goal = st.number_input(
                                "Objetivo",
                                20, 2000, 250,
                                key=f"retry_goal_{item_id}"
                            )
                            retry_margin = st.number_input(
                                "Margen",
                                0, 200, 10,
                                key=f"retry_margin_{item_id}"
                            )
                            retry_min, retry_max = int(retry_goal - retry_margin), int(retry_goal + retry_margin)

                        retry_attempts = st.number_input(
                            "Reintentos",
                            1, 5, 3,
                            key=f"retry_attempts_{item_id}",
                            help="Intentos si no se cumple la longitud"
                        )

                        if st.button("▶️ Iniciar", key=f"retry_btn_{item_id}", type="primary"):
                            with st.spinner("Reescribiendo..."):
                                success, message = retry_rewriting(
                                    it,
                                    username,
                                    retry_min,
                                    retry_max,
                                    retry_attempts
                                )

                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
            else:
                cE.caption("—")

            if btn_count == 0 and not s3_uri:
                cB.caption("—")