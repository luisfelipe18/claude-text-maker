import time
import streamlit as st
from pathlib import Path
from urllib.parse import urlparse
import datetime as dt
import pandas as pd
from boto3.session import Session

from core.repository.csv_repository import CSVNarrativeRepository


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

        rows.append({
            "ID": it.id,
            "Num": getattr(it, "seq", None),
            "Plataforma": _platform_str(it.platform),
            "URL": getattr(it, "url", ""),
            "Palabras": getattr(it, "word_count", None),
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
            seq = getattr(it, "seq", "?")
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
                title = f"**Narración - {seq}: {doc_name}**"
            else:
                title = f"**Narración - {seq}**"

            # Layout: Título + Info + Botones
            cA, cB, cC, cD = st.columns([4, 1.2, 1.2, 1.2])

            # Construir información adicional
            extra_info = ""
            if retry_info:
                extra_info += f" · {retry_info}"
            if problem_info:
                extra_info += f"  \n{problem_info}"

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

            if btn_count == 0 and not s3_uri:
                cB.caption("—")