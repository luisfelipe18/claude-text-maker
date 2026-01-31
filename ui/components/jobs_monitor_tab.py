"""
Pestaña de monitoreo de trabajos asíncronos.
Permite ver el estado de los trabajos en la cola y su progreso.
"""
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.pipeline.job_queue import job_queue, JobStatus
from core.repository.csv_repository import CSVNarrativeRepository
from core.models.enums import ProcessingStatus


def jobs_monitor_tab(username: str):
    st.header("📊 Monitor de Trabajos")

    # Repositorio para cargar narrativas reales
    repo = CSVNarrativeRepository(Path("data/narratives.csv"))

    # Obtener trabajos en cola del usuario
    user_jobs = job_queue.get_user_jobs(username)

    # Obtener narrativas recientes del CSV (últimas 24 horas)
    all_narratives = list(repo.list(user_id=username))
    cutoff_time = datetime.now(ZoneInfo("America/Lima")) - timedelta(hours=24)
    recent_narratives = [
        n for n in all_narratives
        if hasattr(n, 'created_at') and n.created_at and n.created_at > cutoff_time
    ]

    # Separar trabajos activos vs completados
    active_jobs = [j for j in user_jobs if j.status in [JobStatus.PENDING, JobStatus.PROCESSING]]
    completed_job_ids = {j.item.id for j in user_jobs if j.status in [JobStatus.COMPLETED, JobStatus.FAILED]}

    if not user_jobs and not recent_narratives:
        st.info("No tienes trabajos recientes en el sistema.")
        st.caption("💡 Los trabajos completados hace más de 24 horas se pueden ver en 'Explorar Narrativas'")
        return

    # Estadísticas
    col1, col2, col3, col4 = st.columns(4)

    pending = sum(1 for j in user_jobs if j.status == JobStatus.PENDING)
    processing = sum(1 for j in user_jobs if j.status == JobStatus.PROCESSING)
    completed = sum(1 for j in user_jobs if j.status == JobStatus.COMPLETED)
    failed = sum(1 for j in user_jobs if j.status == JobStatus.FAILED)

    col1.metric("⏳ Pendientes", pending)
    col2.metric("🔄 Procesando", processing)
    col3.metric("✅ Completados (24h)", len([n for n in recent_narratives if n.status == ProcessingStatus.COMPLETED]))
    col4.metric("❌ Fallidos", failed)

    # Botón para refrescar
    if st.button("🔄 Refrescar", width="stretch"):
        st.rerun()

    # Botón para limpiar completados/fallidos
    if completed > 0 or failed > 0:
        if st.button("🧹 Limpiar trabajos finalizados de la cola", width="stretch"):
            job_queue.clear_completed(username)
            st.success("Trabajos limpiados de la memoria")
            st.rerun()

    st.divider()

    # === SECCIÓN 1: TRABAJOS ACTIVOS (En cola o procesando) ===
    if active_jobs:
        st.subheader("🔄 Trabajos Activos")

        for job in active_jobs:
            # Color según estado
            if job.status == JobStatus.PROCESSING:
                emoji = "🔄"
                color = "blue"
            else:
                emoji = "⏳"
                color = "orange"

            with st.expander(f"{emoji} **{job.item.url[:60]}...** - {job.status.value.upper()}",
                             expanded=True):

                col_a, col_b = st.columns(2)

                with col_a:
                    st.write(f"**Job ID:** `{job.job_id}`")
                    st.write(f"**URL/Archivo:** {job.item.url}")
                    st.write(f"**Plataforma:** {job.item.platform.value if job.item.platform else 'N/A'}")
                    st.write(f"**Narración #:** {job.item.seq}")
                    st.write(f"**Creado:** {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

                with col_b:
                    st.write(f"**Estado de la Cola:** {job.status.value.upper()}")
                    if job.started_at:
                        st.write(f"**Iniciado:** {job.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        elapsed = (datetime.now(ZoneInfo("America/Lima")) - job.started_at).total_seconds()
                        st.write(f"**Tiempo transcurrido:** {elapsed:.0f}s")

                # Cargar estado actual del CSV
                st.divider()
                st.write("**Estado del Procesamiento:**")

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
                            st.caption(f"📹 Video subido a S3")

                        if current_item.transcript_path:
                            st.caption(f"📝 Transcripción completada")

                        if current_item.word_count:
                            st.write(f"📊 Palabras: **{current_item.word_count}**")

                        if current_item.document_path:
                            st.caption(f"📄 Documento generado")
                    else:
                        st.info("El trabajo aún no ha sido registrado en el sistema")

                except Exception as e:
                    st.error(f"Error al cargar datos: {e}")

        st.divider()

    # === SECCIÓN 2: NARRATIVAS COMPLETADAS RECIENTEMENTE ===
    st.subheader("📚 Narrativas Recientes (Últimas 24 horas)")

    # Ordenar por fecha de creación (más reciente primero)
    recent_narratives.sort(key=lambda n: n.created_at if n.created_at else datetime.min, reverse=True)

    # Filtrar por estado
    filter_status = st.multiselect(
        "Filtrar por estado",
        ["COMPLETED", "FAILED", "PENDING", "DOWNLOADING", "TRANSCRIBING", "REWRITING"],
        default=["PENDING", "DOWNLOADING"]
    )

    narratives_to_show = [
        n for n in recent_narratives
        if n.status.value.upper() in filter_status
    ]

    if not narratives_to_show:
        st.info("No hay narrativas que coincidan con los filtros seleccionados")
    else:
        for narrative in narratives_to_show:
            # Determinar si viene de un job en cola
            from_queue = narrative.id in completed_job_ids

            # Emoji según estado
            if narrative.status == ProcessingStatus.COMPLETED:
                emoji = "✅"
            elif narrative.status == ProcessingStatus.FAILED:
                emoji = "❌"
            else:
                emoji = "🔄"

            # Construir título
            doc_name = None
            if narrative.document_path:
                try:
                    doc_path = Path(narrative.document_path)
                    if doc_path.exists():
                        name = doc_path.stem
                        if name.startswith("video_"):
                            parts = name.split("_", 2)
                            if len(parts) >= 3:
                                doc_name = parts[2]
                except:
                    pass

            title = f"{emoji} **Narración #{narrative.seq}**"
            if doc_name:
                title += f": {doc_name[:50]}"

            with st.expander(title, expanded=False):
                col_a, col_b = st.columns(2)

                with col_a:
                    st.write(f"**ID:** `{narrative.id}`")
                    st.write(f"**Narración #:** {narrative.seq}")
                    st.write(f"**Plataforma:** {narrative.platform.value if narrative.platform else 'N/A'}")
                    if narrative.created_at:
                        st.write(f"**Creado:** {narrative.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    if narrative.completed_at:
                        st.write(f"**Completado:** {narrative.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        if narrative.created_at:
                            duration = (narrative.completed_at - narrative.created_at).total_seconds()
                            st.write(f"**Duración total:** {duration:.0f}s")

                with col_b:
                    st.write(f"**Estado:** {narrative.status.value.upper()}")
                    if narrative.word_count:
                        st.write(f"**📊 Palabras:** {narrative.word_count}")
                    if from_queue:
                        st.caption("🔄 Procesado en esta sesión")

                # URL
                st.write(f"**URL:** {narrative.url}")

                # Botones de descarga
                col_txt, col_doc = st.columns(2)

                # TXT
                if narrative.transcript_path:
                    tpath = Path(narrative.transcript_path)
                    if tpath.exists():
                        try:
                            with open(tpath, "rb") as f:
                                col_txt.download_button(
                                    label="📄 Descargar TXT",
                                    data=f.read(),
                                    file_name=tpath.name,
                                    mime="text/plain",
                                    key=f"dl-txt-{narrative.id}",
                                    width="stretch"
                                )
                        except:
                            col_txt.caption("⚠️ Error al cargar TXT")
                    else:
                        col_txt.caption("📄 TXT no disponible")

                # DOCX
                if narrative.document_path:
                    dpath = Path(narrative.document_path)
                    if dpath.exists():
                        try:
                            with open(dpath, "rb") as f:
                                col_doc.download_button(
                                    label="📘 Descargar DOCX",
                                    data=f.read(),
                                    file_name=dpath.name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl-doc-{narrative.id}",
                                    width="stretch"
                                )
                        except:
                            col_doc.caption("⚠️ Error al cargar DOCX")
                    else:
                        col_doc.caption("📘 DOCX no disponible")

    # Auto-refresh cada 5 segundos si hay trabajos activos
    if pending > 0 or processing > 0:
        st.info("🔄 Esta página se refresca automáticamente cada 5 segundos mientras hay trabajos activos")
        import time
        time.sleep(5)
        st.rerun()
    elif active_jobs:
        st.caption("💡 Refresca manualmente para ver actualizaciones de trabajos activos")

