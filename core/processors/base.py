# --- filepath: video_narrative_processor/core/processors/base.py
from typing import Protocol
from pathlib import Path
from core.models.artifacts import VideoFile, Transcript, RewrittenContent, WordDocument
from core.models.narrative import VideoNarrative

class VideoDownloader(Protocol):
    def download(self, url: str, out_dir: Path) -> VideoFile: ...

class VideoUploader(Protocol):
    def upload(self, local: Path, key: str) -> str: ...  # returns s3 uri

class Transcriber(Protocol):
    def transcribe(self, s3_uri: str, out_dir: Path, job_name: str) -> Transcript: ...

class AIRewriter(Protocol):
    def rewrite(self, transcript_txt: Path, out_dir: Path, min_w: int, max_w: int, max_retries: int = 3) -> RewrittenContent: ...

class WordGenerator(Protocol):
    def build(self, rewritten_json: Path, out_dir: Path, serial: int) -> WordDocument: ...
