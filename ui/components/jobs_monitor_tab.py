"""
Pestaña de monitoreo de trabajos asíncronos.
Permite ver el estado de los trabajos en la cola y su progreso.
"""
import streamlit as st
from pathlib import Path

from core.pipeline.job_queue import job_queue, JobStatus
from core.repository.csv_repository import CSVNarrativeRepository


def jobs_monitor_tab(username: str):
    st.header("📊 Monitor de Trabajos")

    # Obtener todos los trabajos del usuario
    user_jobs = job_queue.get_user_jobs(username)

    if not user_jobs:
        st.info("No tienes trabajos en el sistema.")
        return

    # Estadísticas
    col1, col2, col3, col4 = st.columns(4)

    pending = sum(1 for j in user_jobs if j.status == JobStatus.PENDING)
    processing = sum(1 for j in user_jobs if j.status == JobStatus.PROCESSING)
    completed = sum(1 for j in user_jobs if j.status == JobStatus.COMPLETED)
    failed = sum(1 for j in user_jobs if j.status == JobStatus.FAILED)

    col1.metric("⏳ Pendientes", pending)
    col2.metric("🔄 Procesando", processing)
    col3.metric("✅ Completados", completed)
    col4.metric("❌ Fallidos", failed)

    # Botón para refrescar
    if st.button("🔄 Refrescar", use_container_width=True):
        st.rerun()

    # Botón para limpiar completados/fallidos
    if completed > 0 or failed > 0:
        if st.button("🧹 Limpiar trabajos finalizados", use_container_width=True):
            job_queue.clear_completed(username)
            st.success("Trabajos limpiados")
            st.rerun()

    st.divider()

    # Filtros
    filter_status = st.multiselect(
        "Filtrar por estado",
        ["PENDING", "PROCESSING", "COMPLETED", "FAILED"],
        default=["PENDING", "PROCESSING"]
    )

    # Ordenar por fecha de creación (más recientes primero)
    user_jobs.sort(key=lambda j: j.created_at, reverse=True)

    # Mostrar trabajos
    for job in user_jobs:
        if job.status.value.upper() not in filter_status:
            continue

        # Color según estado
        if job.status == JobStatus.COMPLETED:
            emoji = "✅"
            color = "green"
        elif job.status == JobStatus.FAILED:
            emoji = "❌"
            color = "red"
        elif job.status == JobStatus.PROCESSING:
            emoji = "🔄"
            color = "blue"
        else:
            emoji = "⏳"
            color = "orange"

        with st.expander(f"{emoji} **{job.item.url[:60]}...** - {job.status.value.upper()}",
                         expanded=(job.status == JobStatus.PROCESSING)):

            col_a, col_b = st.columns(2)

            with col_a:
                st.write(f"**Job ID:** `{job.job_id}`")
                st.write(f"**URL/Archivo:** {job.item.url}")
                st.write(f"**Plataforma:** {job.item.platform.value if job.item.platform else 'N/A'}")
                st.write(f"**Creado:** {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

            with col_b:
                st.write(f"**Estado:** {job.status.value.upper()}")
                if job.started_at:
                    st.write(f"**Iniciado:** {job.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if job.completed_at:
                    st.write(f"**Completado:** {job.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    duration = (job.completed_at - job.started_at).total_seconds() if job.started_at else 0
                    st.write(f"**Duración:** {duration:.1f}s")

            # Información adicional del VideoNarrative
            st.divider()
            st.write("**Estado del Procesamiento:**")

            # Cargar datos actuales del repositorio
            repo = CSVNarrativeRepository(Path("data/narratives.csv"))
            try:
                current_item = repo.get(job.item.id)
                if current_item:
                    status_emoji = {
                        "PENDING": "⏳",
                        "DOWNLOADING": "⬇️",
                        "UPLOADED": "☁️",
                        "TRANSCRIBING": "🎙️",
                        "TRANSCRIBED": "📝",
                        "REWRITING": "✍️",
                        "REWRITTEN": "📄",
                        "GENERATING_DOC": "📋",
                        "COMPLETED": "✅",
                        "FAILED": "❌"
                    }

                    current_status = current_item.status.value.upper()
                    st.write(f"{status_emoji.get(current_status, '❓')} **{current_status}**")

                    if current_item.video_s3_url:
                        st.write(f"📹 Video S3: `{current_item.video_s3_url[:80]}...`")

                    if current_item.transcript_path:
                        st.write(f"📝 Transcripción: `{current_item.transcript_path}`")

                    if current_item.word_count:
                        st.write(f"📊 Palabras: {current_item.word_count}")

                    if current_item.document_path:
                        st.write(f"📄 Documento: `{current_item.document_path}`")

                        # Botón de descarga si existe el documento
                        doc_path = Path(current_item.document_path)
                        if doc_path.exists():
                            with open(doc_path, "rb") as f:
                                st.download_button(
                                    label="📥 Descargar Documento",
                                    data=f,
                                    file_name=doc_path.name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_{job.job_id}"
                                )
                else:
                    st.warning("No se encontró información del item en el repositorio")

            except Exception as e:
                st.error(f"Error al cargar datos: {e}")

            # Mostrar error si falló
            if job.error_message:
                st.error(f"**Error:** {job.error_message}")

    # Auto-refresh cada 10 segundos si hay trabajos activos
    if pending > 0 or processing > 0:
        st.info("🔄 Esta página se refresca automáticamente cada 10 segundos")
        import time
        time.sleep(10)
        st.rerun()
