import streamlit as st
from pathlib import Path

from core.pipeline.factory import ProcessorFactory
from core.pipeline.processor import NarrativeProcessor
from core.models.configs import ProcessingConfig, RewriteConfig
from core.models.enums import Platform
from core.repository.csv_repository import CSVNarrativeRepository
from core.repository.file_manager import FileManager
from utils.logging import setup_logging

from utils.file_utils import sanitize_filename


def generate_tab(username: str):
    st.header("Generar Narrativas")

    fuente = st.radio("Fuente", ["URLs", "Archivos (.mp4)"], index=0, horizontal=True)

    # Longitud objetivo
    words_mode = st.selectbox("Palabras objetivo", ["TikTok (250 ±10)", "Facebook (550 ±10)", "Personalizado"], index=0)
    if words_mode.startswith("TikTok"):
        min_w, max_w = 240, 260
    elif words_mode.startswith("Facebook"):
        min_w, max_w = 540, 560
    else:
        goal = st.number_input("Objetivo", 100, 2000, 250)
        margin = st.number_input("Margen", 0, 200, 10)
        min_w, max_w = int(goal - margin), int(goal + margin)

    # Configuración de reintentos
    max_retries = st.number_input(
        "Reintentos máximos (si no se cumple la longitud)",
        min_value=1,
        max_value=5,
        value=3,
        help="Número de veces que el sistema intentará ajustar la longitud del texto si no cumple con las palabras objetivo"
    )

    # Ingesta
    urls = ""
    files = []
    up_platform = Platform.FACEBOOK
    if fuente == "URLs":
        urls = st.text_area("Pega URLs (una por línea)", height=140, placeholder="https://...\nhttps://...")
    else:
        files = st.file_uploader("Sube uno o varios .mp4", type=["mp4"], accept_multiple_files=True)
        up_platform = Platform(
            st.selectbox("Plataforma (para archivos subidos)", [Platform.VIDEO], index=0)  # VIDEO por defecto
        )

    # Paths y logging
    run_dir = Path("runs") / username
    setup_logging(run_dir / "logs")

    if st.button("Iniciar Procesamiento", type="primary"):
        # Configs
        pconf = ProcessingConfig(
            run_dir=run_dir,
            bucket=st.secrets.get("S3_BUCKET", "guiones"),
            s3_prefix=st.secrets.get("S3_PREFIX", "videos/"),
            region=st.secrets.get("AWS_REGION", "us-east-1"),
            enable_aws=True,
        )
        tpl = st.session_state.get("prompt_template")
        rconf = RewriteConfig(
            model_name=st.secrets.get("OPENAI_MODEL", "gpt-5"),
            min_words=min_w,
            max_words=max_w,
            language=st.session_state.get("lang", "ES"),
            max_retries=max_retries,
            prompt_template=tpl,
        )

        repo = CSVNarrativeRepository(Path("data/narratives.csv"))
        fm = FileManager(Path("."), username)
        factory = ProcessorFactory(pconf, rconf)
        proc = NarrativeProcessor(
            pconf, rconf, repo, fm,
            factory.build_downloader(),
            factory.build_uploader(),
            factory.build_transcriber(),
            factory.build_rewriter(),
            factory.build_docgen(),
        )

        if fuente == "URLs":
            url_list = [u.strip() for u in (urls or "").splitlines() if u.strip()]
            if not url_list:
                st.warning("No ingresaste URLs.")
                return
            for i, url in enumerate(url_list, start=1):
                item = proc.new_item(username, url)
                with st.status(f"Procesando URL #{i}: {url}", expanded=True) as status:
                    try:
                        res = proc.process_one(item)
                        st.success(f"#{i} COMPLETADO → {res.document_path}")
                    except Exception as e:
                        st.error(f"#{i} FALLÓ: {e}")
                    finally:
                        status.update(label=f"#{i} finalizado", state="complete")
        else:
            if not files:
                st.warning("No subiste archivos .mp4.")
                return

            # ✅ Crear carpeta de uploads si no existe
            uploads_dir = run_dir / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            for i, uf in enumerate(files, start=1):
                local_path = uploads_dir / uf.name
                with open(local_path, "wb") as f:
                    f.write(uf.read())

                # Registramos item con pseudo-URL para trazabilidad y plataforma elegida
                item = proc.new_item(username, url=f"upload://{uf.name}")
                item.platform = up_platform

                with st.status(f"Procesando Archivo #{i}: {uf.name}", expanded=True) as status:
                    try:
                        res = proc.process_local_video(item, local_path)
                        st.success(f"#{i} COMPLETADO → {res.document_path}")
                    except Exception as e:
                        item.status = item.status.FAILED; repo.update(item)
                        st.error(f"#{i} FALLÓ: {e}")
                    finally:
                        status.update(label=f"#{i} finalizado", state="complete")
