# --- filepath: video_narrative_processor/core/models/artifacts.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class VideoFile:
    local_path: Path
    s3_key: Optional[str] = None

@dataclass
class Transcript:
    text_path: Path

@dataclass
class RewrittenContent:
    json_path: Path
    words_count: int

@dataclass
class WordDocument:
    docx_path: Path