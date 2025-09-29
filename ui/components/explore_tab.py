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

def _presign(bucket: str, key: str, *, region: str, ak: str | None, sk: str | None, tk: str | None, expires: int = 3600) -> str | None:
    try:
        if ak or sk or tk:
            session = Session(aws_access_key_id=ak, aws_secret_access_key=sk, aws_session_token=tk, region_name=region)
        else:
            session = Session(region_name=region)
        s3 = session.client("s3")
        return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)
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
    items = list(repo.list(user_id=username))  # Solo del usuario actual
    if not items:
        st.info("Sin registros por ahora.")
        return

    # ---- Filtros ----
    c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 2.3, 1.1, 1.5])

    with c1:
        estados_all = sorted({_status_str(it.status) for it in items if getattr(it, "status", None)})
        estado_sel = st.selectbox("Estado", ["Todos"] + estados_all, index=0)

    with c2:
        plataformas_all = sorted({_platform_str(it.platform) for it in items if getattr(it, "platform", None)})
        plataforma_sel = st.selectbox("Plataforma", ["Todas"] + plataformas_all, index=0)

    with c3:
        hoy = dt.date.today()
        app_start = _get_app_start_date()
        app_start = min(app_start, hoy)
        rango = st.date_input(
            "Rango de fechas (creación)",
            value=(app_start, hoy),
            min_value=app_start,
            max_value=hoy,
        )

    with c4:
        ultimos_10 = st.checkbox("Solo últimas 10", value=True)

    with c5:
        solo_completos = st.checkbox("Solo estado COMPLETED", value=False)

    # ---- Aplicar filtros ----
    start, end = rango

    def _in_rango(it):
        created = getattr(it, "created_at", None)
        if isinstance(created, dt.datetime):
            cd = created.date()
            return start <= cd <= end
        return True

    filtered = []
    for it in items:
        st_txt = _status_str(getattr(it, "status", None))
        pl_txt = _platform_str(getattr(it, "platform", None))

        if solo_completos:
            if st_txt != "COMPLETED":
                continue
        elif estado_sel != "Todos" and st_txt != estado_sel:
            continue

        if plataforma_sel != "Todas" and pl_txt != plataforma_sel:
            continue

        if not _in_rango(it):
            continue

        filtered.append(it)

    filtered.sort(key=lambda x: getattr(x, "created_at", dt.datetime.min), reverse=True)
    if ultimos_10 and len(filtered) > 10:
        filtered = filtered[:10]

    # ---- Tabla (Arrow-safe) ----
    rows = []
    for it in filtered:
        rows.append({
            "ID": it.id,
            "Plataforma": _platform_str(it.platform),
            "URL": getattr(it, "url", ""),
            "Palabras": getattr(it, "word_count", None),
            "Estado": _status_str(it.status),
            "Creado": getattr(it, "created_at", None),
            "Video S3": getattr(it, "video_s3_url", None),
            "Transcript (txt)": getattr(it, "transcript_path", None),
            "Documento (docx)": getattr(it, "document_path", None),
        })
    safe_rows = [{k: _to_arrow_safe(v) for k, v in r.items()} for r in rows]
    df = pd.DataFrame(safe_rows)
    st.dataframe(df, width='stretch', hide_index=True)

    # ---- Acciones (coherentes con el subconjunto filtrado) ----
    st.markdown("### Acciones")
    ak = st.secrets.get("AWS_ACCESS_KEY_ID")
    sk = st.secrets.get("AWS_SECRET_ACCESS_KEY")
    tk = st.secrets.get("AWS_SESSION_TOKEN")
    region = st.secrets.get("AWS_REGION", "us-east-1")

    for it in filtered:
        with st.container(border=True):
            cA, cB, cC, cD = st.columns([4, 1.2, 1.2, 1.2])
            created_str = _to_arrow_safe(getattr(it, "created_at", ""))

            cA.markdown(
                f"**{_platform_str(it.platform)}** · [{getattr(it, 'url', '')}]({getattr(it, 'url', '')})  \n"
                f"**Estado:** {_status_str(it.status)} · **Creado:** {created_str} · "
                f"**Palabras:** {getattr(it, 'word_count', '—') or '—'}"
            )

            btn_count = 0

            # 📹 Video (S3 presigned)
            s3_uri = getattr(it, "video_s3_url", None)
            if s3_uri:
                bkt, key = _parse_s3_uri(s3_uri)
                if bkt and key:
                    url = _presign(bkt, key, region=region, ak=ak, sk=sk, tk=tk)
                    if url:
                        # key único por narrativa
                        cB.link_button("📹 Video", url)
                        btn_count += 1

            # 📄 TXT
            tpath = getattr(it, "transcript_path", None)
            if tpath and Path(tpath).exists():
                with open(tpath, "rb") as f:
                    cC.download_button(
                        "📄 TXT",
                        data=f.read(),
                        file_name=Path(tpath).name,
                        mime="text/plain",
                        key=f"dl-txt-{it.id}",
                    )
                    btn_count += 1

            # 📘 DOCX
            dpath = getattr(it, "document_path", None)
            if dpath and Path(dpath).exists():
                with open(dpath, "rb") as f:
                    cD.download_button(
                        "📘 DOCX",
                        data=f.read(),
                        file_name=Path(dpath).name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl-doc-{it.id}",                    )
                    btn_count += 1

            if btn_count == 0:
                cB.caption("—"); cC.caption("—"); cD.caption("—")
