# --- filepath: video_narrative_processor/core/processors/transcriber.py
from pathlib import Path
import json, urllib.parse, urllib.request, io, boto3

from core.processors.base import Transcriber
from infrastructure.aws.s3_client import S3Client
from infrastructure.aws.transcribe_client import TranscribeClient
from core.models.artifacts import Transcript

class AWSTranscriber(Transcriber):
    def __init__(
            self,
            bucket: str,
            prefix: str,
            region: str,
            output_prefix: str | None = None,
            aws_access_key_id: str | None = None,
            aws_secret_access_key: str | None = None
    ):
        self.s3 = S3Client(
            bucket=bucket,
            region=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,

        )
        self.tr = TranscribeClient(
            region=region,
            output_bucket=bucket,
            output_prefix=output_prefix,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        self.prefix = prefix.rstrip("/") + "/"
        self._region = region

    def _download_transcript_json(self, uri: str) -> dict:
        """Descarga el JSON de transcript desde HTTPS (AWS hosted) o S3 y retorna el dict."""

        if uri.startswith("s3://"):
            parts = urllib.parse.urlparse(uri)
            bucket = parts.netloc
            key = parts.path.lstrip("/")
            bio = io.BytesIO()
            self.s3.client.download_fileobj(bucket, key, bio)
            bio.seek(0)
            return json.loads(bio.read().decode("utf-8"))
        # HTTPS estándar alojado por AWS Transcribe
        with urllib.request.urlopen(uri) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def transcribe(self, s3_uri: str, out_dir: Path, job_name: str) -> Transcript:
        # Espera a que termine el job y guarda el JSON de metadatos
        job_json_path = self.tr.start_and_wait(job_name, s3_uri, out_dir)
        meta = json.loads(job_json_path.read_text(encoding="utf-8"))
        uri = meta["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        # Descarga el JSON de transcript verdadero
        tr_json = self._download_transcript_json(uri)
        text = ""
        try:
            texts = tr_json.get("results", {}).get("transcripts", [])
            if texts:
                text = texts[0].get("transcript", "")
        except Exception:
            text = ""
        # Persistir TXT real (o advertencia)
        out_dir.mkdir(parents=True, exist_ok=True)
        txt = out_dir / f"{job_name}.txt"
        if text.strip():
            txt.write_text(text, encoding="utf-8")
        else:
            txt.write_text("[WARN] Transcript vacío o no disponible. Verifica configuración de Transcribe/S3.",
                           encoding="utf-8")
        return Transcript(text_path=txt)
