# --- filepath: video_narrative_processor/infrastructure/aws/transcribe_client.py
import time, json
from pathlib import Path
from datetime import datetime

import boto3

from utils.exceptions import TranscribeError

def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    raise TypeError(...)

class TranscribeClient:
    def __init__(
            self,
            region: str = "us-east-1",
            output_bucket: str | None = None,
            output_prefix: str | None = None,
            aws_access_key_id: str | None = None,
            aws_secret_access_key: str | None = None
    ):
        if aws_access_key_id and aws_secret_access_key:
            session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region,
            )
            self.client = session.client("transcribe")
        else:
            self.client = boto3.client("transcribe", region_name=region)
        self.output_bucket = output_bucket
        self.output_prefix = (output_prefix or "").lstrip("/") if output_prefix else None

    def start_and_wait(self, job_name: str, media_uri: str, out_dir: Path) -> Path:
        try:
            self.client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": media_uri},
                MediaFormat="mp4",
                LanguageCode="es-ES",
            )
        except self.client.exceptions.ConflictException:
            pass
        while True:
            resp = self.client.get_transcription_job(TranscriptionJobName=job_name)
            st = resp["TranscriptionJob"]["TranscriptionJobStatus"]
            if st in ("COMPLETED", "FAILED"):
                break
            time.sleep(8)
        if st == "FAILED":
            raise TranscribeError(f"Transcribe job {job_name} failed")
        uri = resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        # when output bucket is not set, AWS hosts it. We'll fetch via boto (signed url not needed for public temp)
        # But for simplicity we expect S3 output to be configured externally.
        # Here we only return a placeholder path; UI layer may fetch via S3 key when configured.
        p = out_dir / f"{job_name}.json"
        p.write_text(
            json.dumps(
                resp,
                default=_json_default,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )
        return p