# --- filepath: video_narrative_processor/core/models/narrative.py
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
from core.models.enums import Platform, ProcessingStatus
from pathlib import Path

@dataclass
class VideoNarrative:
    id: str
    user_id: str
    url: str
    platform: Platform
    seq: int = 0
    status: ProcessingStatus = ProcessingStatus.PENDING
    title: str | None = None
    word_count: int | None = None
    video_s3_url: str | None = None
    transcript_path: Path | None = None
    document_path: Path | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(ZoneInfo("America/Lima")))
    completed_at: datetime | None = None