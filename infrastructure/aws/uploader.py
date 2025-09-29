from pathlib import Path
from core.processors.base import VideoUploader
from infrastructure.aws.s3_client import S3Client

class S3Uploader(VideoUploader):
    def __init__(self, bucket: str, region: str = "us-east-1"):
        self.s3 = S3Client(bucket=bucket, region=region)

    def upload(self, local: Path, key: str) -> str:
        # Devuelve s3://bucket/key
        return self.s3.upload_file(local, key)
