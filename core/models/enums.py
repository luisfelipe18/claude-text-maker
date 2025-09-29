# --- filepath: video_narrative_processor/core/models/enums.py
from enum import Enum, auto

class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    UPLOADED = "UPLOADED"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    REWRITING = "REWRITING"
    REWRITTEN = "REWRITTEN"
    GENERATING_DOC = "GENERATING_DOC"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Platform(str, Enum):
    YOUTUBE = "YouTube"
    TIKTOK = "TikTok"
    FACEBOOK = "Facebook"
    INSTAGRAM = "Instagram"
    VIDEO = "Video"
    UNKNOWN = "Unknown"

class AIModel(str, Enum):
    CLAUDE4 = "Claude 4"
    GPT5 = "ChatGPT 5"