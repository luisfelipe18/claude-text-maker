# --- filepath: video_narrative_processor/infrastructure/aws/s3_client.py
from pathlib import Path
import mimetypes

from boto3.session import Session
from boto3 import client as boto3_client


class S3Client:
    def __init__(
            self,
            bucket: str,
            region: str = "us-east-1",
            aws_access_key_id: str | None = None,
            aws_secret_access_key: str | None = None
    ):
        self.bucket = bucket

        if aws_access_key_id and aws_secret_access_key:
            session = Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region,
            )
            self.client = session.client("s3")
        else:
            self.client = boto3_client("s3", region_name=region)


    def upload_file(self, local: Path, key: str) -> str:
        mime, _ = mimetypes.guess_type(str(local))
        extra = {"ContentType": mime} if mime else None
        self.client.upload_file(str(local), self.bucket, key, ExtraArgs=(extra or {}))
        return f"s3://{self.bucket}/{key}"

    def download_file(self, key: str, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(dest))

