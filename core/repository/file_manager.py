# --- filepath: video_narrative_processor/core/repository/file_manager.py
from pathlib import Path
from core.models.narrative import VideoNarrative

class FileManager:
    def __init__(self, base_dir: Path, username: str):
        self.base = base_dir / "data" / "users" / username
        self.transcripts = self.base / "transcripts"
        self.documents = self.base / "documents"
        self.base.mkdir(parents=True, exist_ok=True)
        self.transcripts.mkdir(parents=True, exist_ok=True)
        self.documents.mkdir(parents=True, exist_ok=True)
