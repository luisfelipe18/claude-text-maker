# --- filepath: video_narrative_processor/core/pipeline/processor.py
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from core.models.enums import ProcessingStatus, Platform
from core.models.narrative import VideoNarrative
from core.models.configs import ProcessingConfig, RewriteConfig
from core.repository.csv_repository import CSVNarrativeRepository
from core.repository.file_manager import FileManager
from core.processors.base import VideoDownloader, VideoUploader, Transcriber, AIRewriter, WordGenerator
from utils.file_utils import sanitize_filename

class NarrativeProcessor:
    def __init__(self, pconf: ProcessingConfig, rconf: RewriteConfig, repo: CSVNarrativeRepository, fm: FileManager,
                 downloader: VideoDownloader, uploader: VideoUploader, transcriber: Transcriber, rewriter: AIRewriter,
                 docgen: WordGenerator):
        self.platform = None
        self.pconf = pconf
        self.rconf = rconf
        self.repo = repo
        self.fm = fm
        self.downloader = downloader
        self.uploader = uploader
        self.transcriber = transcriber
        self.rewriter = rewriter
        self.docgen = docgen
        self.run_dir = pconf.run_dir
        self.videos_dir = self.run_dir / "videos"
        self.uploads_dir = self.run_dir / "uploads"
        self.textos_dir = self.run_dir / "textos"
        self.raw_txt_dir = self.textos_dir / "raw_txt"
        self.rewritten_dir = self.textos_dir / "rewritten_json"
        self.words_dir = self.run_dir / "words"

        for d in (self.videos_dir, self.raw_txt_dir, self.rewritten_dir, self.words_dir):
            d.mkdir(parents=True, exist_ok=True)

        self._s3_prefix = (self.pconf.s3_prefix or "").lstrip("/").rstrip("/") + "/"

    def _next_serial(self, user_id: str) -> int:
        """Obtiene el próximo número de secuencia para un usuario.
        Busca el máximo actual en el repositorio (incluyendo trabajos pendientes)."""
        max_seq = 0
        for it in self.repo.list(user_id=user_id):
            try:
                if getattr(it, "seq", 0) and it.seq > max_seq:
                    max_seq = it.seq
            except Exception as e:
                print(e)
                pass
        return max_seq + 1
    
    def _reserve_sequential_numbers(self, user_id: str, count: int) -> list[int]:
        """Reserva una secuencia de números consecutivos para múltiples videos.
        Retorna una lista de números de secuencia [n, n+1, n+2, ...]"""
        start_seq = self._next_serial(user_id)
        return list(range(start_seq, start_seq + count))

    def detect_platform(self, url: str) -> Platform:
        u = url.lower()
        self.platform = Platform.UNKNOWN
        if "youtube" in u or "youtu.be" in u:
            self.platform = Platform.YOUTUBE
        if "tiktok.com" in u: 
            self.platform = Platform.TIKTOK
        if "facebook.com" in u or "fb.watch" in u: 
            self.platform = Platform.FACEBOOK
        if "instagram.com" in u: 
            self.platform = Platform.INSTAGRAM
        return self.platform

    def new_item(self, user_id: str, url: str) -> VideoNarrative:
        iid = uuid.uuid4().hex[:12]
        seq = self._next_serial(user_id)
        return VideoNarrative(id=iid, user_id=user_id, url=url, platform=self.detect_platform(url), seq=seq)

    def new_item_for_upload(self, user_id: str, local_name: str,
                            platform: Platform = Platform.UNKNOWN) -> VideoNarrative:
        iid = uuid.uuid4().hex[:12]
        seq = self._next_serial(user_id)
        pseudo_url = f"upload://{local_name}"
        return VideoNarrative(id=iid, user_id=user_id, url=pseudo_url, platform=platform, seq=seq)

    def process_one(self, item: VideoNarrative) -> VideoNarrative:
        """Procesa un video completo con manejo de errores robusto por etapa."""

        try:
            # 1) Download
            item.status = ProcessingStatus.DOWNLOADING
            self.repo.save(item)

            try:
                vf = self.downloader.download(item.url, self.videos_dir)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error en descarga: {str(e)}"
                self.repo.update(item)
                raise  # Re-lanzar para que JobQueue lo maneje

            # 2) Upload a S3
            try:
                key = f"{self._s3_prefix}{vf.local_path.name}"
                s3_uri = self.uploader.upload(vf.local_path, key)

                # Limpieza local del video tras subir
                try:
                    vf.local_path.unlink()
                except Exception as e:
                    print(f"[WARN] No se pudo eliminar archivo local: {e}")

                item.status = ProcessingStatus.UPLOADED
                item.video_s3_url = s3_uri
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error subiendo a S3: {str(e)}"
                self.repo.update(item)
                raise

            # 3) Transcribe
            try:
                item.status = ProcessingStatus.TRANSCRIBING
                self.repo.update(item)
                tr = self.transcriber.transcribe(item.video_s3_url, self.raw_txt_dir, job_name=f"job-{item.id}")
                item.status = ProcessingStatus.TRANSCRIBED
                item.transcript_path = tr.text_path
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error en transcripción: {str(e)}"
                self.repo.update(item)
                raise

            # 4) Rewrite
            try:
                item.status = ProcessingStatus.REWRITING
                self.repo.update(item)
                rw = self.rewriter.rewrite(
                    tr.text_path,
                    self.rewritten_dir,
                    self.rconf.min_words,
                    self.rconf.max_words,
                    self.rconf.max_retries
                )
                item.status = ProcessingStatus.REWRITTEN
                item.word_count = rw.words_count
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error en reescritura: {str(e)}"
                self.repo.update(item)
                raise

            # 5) Generate DOCX
            try:
                item.status = ProcessingStatus.GENERATING_DOC
                self.repo.update(item)
                doc = self.docgen.build(
                    rw.json_path,
                    self.words_dir,
                    serial=item.seq
                )
                item.status = ProcessingStatus.COMPLETED
                item.document_path = doc.docx_path
                item.completed_at = datetime.now(ZoneInfo("America/Lima"))
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error generando documento: {str(e)}"
                self.repo.update(item)
                raise

            return item

        except Exception as e:
            # Error general - ya debería estar manejado arriba, pero por si acaso
            if item.status != ProcessingStatus.FAILED:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error inesperado: {str(e)}"
                self.repo.update(item)
            raise  # Re-lanzar para JobQueue

    def process_local_video(self, item: VideoNarrative, local_path: Path) -> VideoNarrative:
        """Procesa un video local con manejo de errores robusto por etapa."""

        try:
            # 1) Guardar registro inicial
            item.status = ProcessingStatus.DOWNLOADING
            self.repo.save(item)

            # 2) Subir a S3 con nombre seguro + sufijo único
            try:
                safe_name = sanitize_filename(local_path.stem) or "video"
                ext = local_path.suffix.lower() or ".mp4"
                key = f"{self.pconf.s3_prefix}{safe_name}_{item.id}{ext}"
                s3_uri = self.uploader.upload(local_path, key)

                item.status = ProcessingStatus.UPLOADED
                item.video_s3_url = s3_uri
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error subiendo a S3: {str(e)}"
                self.repo.update(item)
                raise

            # 3) Transcribe
            try:
                item.status = ProcessingStatus.TRANSCRIBING
                self.repo.update(item)
                tr = self.transcriber.transcribe(s3_uri, self.raw_txt_dir, job_name=f"job-{item.id}")
                item.status = ProcessingStatus.TRANSCRIBED
                item.transcript_path = tr.text_path
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error en transcripción: {str(e)}"
                self.repo.update(item)
                raise

            # 4) Rewriter
            try:
                item.status = ProcessingStatus.REWRITING
                self.repo.update(item)
                rw = self.rewriter.rewrite(
                    tr.text_path,
                    self.rewritten_dir,
                    self.rconf.min_words,
                    self.rconf.max_words,
                    self.rconf.max_retries
                )
                item.status = ProcessingStatus.REWRITTEN
                item.word_count = rw.words_count
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error en reescritura: {str(e)}"
                self.repo.update(item)
                raise

            # 5) DOCX
            try:
                item.status = ProcessingStatus.GENERATING_DOC
                self.repo.update(item)
                doc = self.docgen.build(
                    rw.json_path,
                    self.words_dir,
                    serial=item.seq
                )
                item.status = ProcessingStatus.COMPLETED
                item.document_path = doc.docx_path
                item.completed_at = datetime.now(ZoneInfo("America/Lima"))
                self.repo.update(item)
            except Exception as e:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error generando documento: {str(e)}"
                self.repo.update(item)
                raise

            return item

        except Exception as e:
            # Error general - ya debería estar manejado arriba, pero por si acaso
            if item.status != ProcessingStatus.FAILED:
                item.status = ProcessingStatus.FAILED
                item.error_message = f"Error inesperado: {str(e)}"
                self.repo.update(item)
            raise  # Re-lanzar para JobQueue
