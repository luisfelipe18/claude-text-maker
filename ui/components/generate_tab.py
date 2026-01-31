import streamlit as st
from pathlib import Path
import uuid

from core.pipeline.factory import ProcessorFactory
from core.pipeline.processor import NarrativeProcessor
from core.pipeline.job_queue import job_queue, Job
from core.models.configs import ProcessingConfig, RewriteConfig
from core.models.enums import Platform
from core.repository.csv_repository import CSVNarrativeRepository
from core.repository.file_manager import FileManager
from utils.logging import setup_logging


def generate_tab(username: str):
    st.header("Generar Narrativas")

    fuente = st.radio("Fuente", ["URLs", "Archivos (.mp4)"], index=0, horizontal=True)

    # Longitud objetivo
    words_mode = st.selectbox("Palabras objetivo", ["TikTok (250 ±10)", "Facebook (530 ±10)", "Personalizado"], index=0)
    if words_mode.startswith("TikTok"):
        min_w, max_w = 240, 260
    elif words_mode.startswith("Facebook"):
        min_w, max_w = 520, 540
    else:
        goal = st.number_input("Objetivo", 20, 2000, 250)
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

    # Mostrar estado de la cola
    pending = job_queue.get_pending_count(username)
    if pending > 0:
        st.info(f"📋 Tienes **{pending}** trabajo(s) en cola o procesando")

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

        # Configurar el procesador en la cola y asegurar que el worker esté corriendo
        job_queue.set_processor(proc)
        job_queue.start_worker()

        if fuente == "URLs":
            url_list = [u.strip() for u in (urls or "").splitlines() if u.strip()]
            if not url_list:
                st.warning("No ingresaste URLs.")
                return

            # Reservar números de secuencia consecutivos ANTES de crear los items
            seq_numbers = proc._reserve_sequential_numbers(username, len(url_list))

            # Encolar trabajos en background con números pre-asignados
            job_info = []  # Lista de tuplas (job_id, seq)
            for i, (url, seq) in enumerate(zip(url_list, seq_numbers)):
                item = proc.new_item(username, url)
                item.seq = seq  # Forzar el número reservado
                job_id = f"{username}_{uuid.uuid4().hex[:8]}"
                job = Job(job_id, item, username, is_upload=False)
                job_queue.add_job(job)
                job_info.append((job_id, seq))

            # Mostrar rango de números asignados
            if len(seq_numbers) == 1:
                st.success(f"✅ Video agregado a la cola → **Narrativa #{seq_numbers[0]}**")
            else:
                st.success(f"✅ {len(url_list)} videos agregados → **Narrativas #{min(seq_numbers)} a #{max(seq_numbers)}**")

            st.info("🔄 Los videos se están procesando en background. Puedes cerrar esta página y ver el progreso en 'Monitor de Trabajos'.")

            # Mostrar números de narrativa
            with st.expander("📋 Ver detalle de números asignados"):
                for job_id, seq in job_info:
                    st.code(f"Narrativa #{seq} (Job ID: {job_id})")
        else:
            if not files:
                st.warning("No subiste archivos .mp4.")
                return

            # ✅ Crear carpeta de uploads si no existe
            uploads_dir = run_dir / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            # Reservar números de secuencia consecutivos ANTES de crear los items
            seq_numbers = proc._reserve_sequential_numbers(username, len(files))

            # Guardar archivos y encolar trabajos con números pre-asignados
            job_info = []  # Lista de tuplas (job_id, seq, filename)
            for i, (uf, seq) in enumerate(zip(files, seq_numbers)):
                local_path = uploads_dir / uf.name
                with open(local_path, "wb") as f:
                    f.write(uf.read())

                item = proc.new_item(username, url=f"upload://{uf.name}")
                item.seq = seq  # Forzar el número reservado
                item.platform = up_platform

                job_id = f"{username}_{uuid.uuid4().hex[:8]}"
                job = Job(job_id, item, username, local_path=local_path, is_upload=True)
                job_queue.add_job(job)
                job_info.append((job_id, seq, uf.name))

            # Mostrar rango de números asignados
            if len(seq_numbers) == 1:
                st.success(f"✅ Archivo agregado a la cola → **Narrativa #{seq_numbers[0]}**")
            else:
                st.success(f"✅ {len(files)} archivos agregados → **Narrativas #{min(seq_numbers)} a #{max(seq_numbers)}**")

            st.info("🔄 Los videos se están procesando en background. Puedes cerrar esta página y ver el progreso en 'Monitor de Trabajos'.")

            with st.expander("📋 Ver detalle de números asignados"):
                for job_id, seq, filename in job_info:
                    st.code(f"Narrativa #{seq} - {filename} (Job ID: {job_id})")


