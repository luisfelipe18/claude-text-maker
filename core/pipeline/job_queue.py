"""
Sistema de cola de trabajos para procesamiento asíncrono.
Usa threading y persistencia en JSON para recuperación de estado.
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo
from enum import Enum

from core.models.narrative import VideoNarrative


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job:
    """Representa un trabajo de procesamiento."""
    def __init__(self, job_id: str, item: VideoNarrative, user_id: str,
                 local_path: Optional[Path] = None, is_upload: bool = False):
        self.job_id = job_id
        self.item = item
        self.user_id = user_id
        self.local_path = local_path
        self.is_upload = is_upload
        self.status = JobStatus.PENDING
        self.error_message: Optional[str] = None
        self.created_at = datetime.now(ZoneInfo("America/Lima"))
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "item_id": self.item.id,
            "user_id": self.user_id,
            "url": self.item.url,
            "platform": self.item.platform.value if self.item.platform else None,
            "status": self.status.value,
            "error_message": self.error_message,
            "is_upload": self.is_upload,
            "local_path": str(self.local_path) if self.local_path else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class JobQueue:
    """Cola de trabajos con persistencia y procesamiento en background."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.queue = Queue()
        self.jobs: Dict[str, Job] = {}
        self.jobs_lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None
        self.processor = None  # Se inyectará desde fuera
        self.is_running = False
        self.persistence_path = Path("data/job_queue.json")
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

        # Cargar trabajos pendientes
        self._load_state()

    def set_processor(self, processor):
        """Inyecta el procesador que ejecutará los trabajos."""
        self.processor = processor

    def start_worker(self):
        """Inicia el worker en background si no está corriendo."""
        if self.is_running:
            return

        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("[JobQueue] Worker iniciado")

    def stop_worker(self):
        """Detiene el worker gracefully."""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        print("[JobQueue] Worker detenido")

    def add_job(self, job: Job) -> str:
        """Agrega un trabajo a la cola."""
        with self.jobs_lock:
            self.jobs[job.job_id] = job
            self.queue.put(job)
            self._save_state()
        print(f"[JobQueue] Job {job.job_id} agregado a la cola")
        return job.job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """Obtiene información de un trabajo."""
        with self.jobs_lock:
            return self.jobs.get(job_id)

    def get_user_jobs(self, user_id: str) -> List[Job]:
        """Obtiene todos los trabajos de un usuario."""
        with self.jobs_lock:
            return [job for job in self.jobs.values() if job.user_id == user_id]

    def get_pending_count(self, user_id: Optional[str] = None) -> int:
        """Cuenta trabajos pendientes."""
        with self.jobs_lock:
            jobs = self.jobs.values()
            if user_id:
                jobs = [j for j in jobs if j.user_id == user_id]
            return sum(1 for j in jobs if j.status in [JobStatus.PENDING, JobStatus.PROCESSING])

    def _worker_loop(self):
        """Loop principal del worker que procesa trabajos."""
        print("[JobQueue] Worker loop iniciado")
        while self.is_running:
            try:
                # Timeout para poder verificar is_running periódicamente
                job = self.queue.get(timeout=1.0)
            except Empty:
                continue

            if not self.processor:
                print("[JobQueue] ERROR: No hay procesador configurado")
                job.status = JobStatus.FAILED
                job.error_message = "No processor configured"
                self._save_state()
                continue

            # Procesar el trabajo
            with self.jobs_lock:
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.now(ZoneInfo("America/Lima"))
                self._save_state()

            print(f"[JobQueue] Procesando job {job.job_id}: {job.item.url}")

            try:
                if job.is_upload and job.local_path:
                    self.processor.process_local_video(job.item, job.local_path)
                else:
                    self.processor.process_one(job.item)

                with self.jobs_lock:
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(ZoneInfo("America/Lima"))
                    print(f"[JobQueue] Job {job.job_id} COMPLETADO")

            except Exception as e:
                with self.jobs_lock:
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    print(f"[JobQueue] Job {job.job_id} FALLÓ: {e}")

            finally:
                with self.jobs_lock:
                    self._save_state()
                self.queue.task_done()

    def _save_state(self):
        """Persiste el estado de la cola en disco."""
        try:
            state = {
                "jobs": {job_id: job.to_dict() for job_id, job in self.jobs.items()},
                "updated_at": datetime.now(ZoneInfo("America/Lima")).isoformat()
            }
            self.persistence_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[JobQueue] Error guardando estado: {e}")

    def _load_state(self):
        """Carga el estado previo desde disco (para recuperación)."""
        if not self.persistence_path.exists():
            return

        try:
            state = json.loads(self.persistence_path.read_text(encoding="utf-8"))
            # Solo cargamos metadata para mostrar estado, no re-encolamos
            # (los jobs en PENDING se pueden re-encolar manualmente si se desea)
            print(f"[JobQueue] Estado cargado: {len(state.get('jobs', {}))} trabajos históricos")
        except Exception as e:
            print(f"[JobQueue] Error cargando estado: {e}")

    def clear_completed(self, user_id: Optional[str] = None):
        """Limpia trabajos completados/fallidos para liberar memoria."""
        with self.jobs_lock:
            to_remove = []
            for job_id, job in self.jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                    if user_id is None or job.user_id == user_id:
                        to_remove.append(job_id)

            for job_id in to_remove:
                del self.jobs[job_id]

            if to_remove:
                self._save_state()
                print(f"[JobQueue] {len(to_remove)} trabajos limpiados")


# Singleton global
job_queue = JobQueue()
