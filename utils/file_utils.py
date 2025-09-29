# --- filepath: video_narrative_processor/utils/file_utils.py
from pathlib import Path
import shutil
import re

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def sanitize_filename(text: str, max_len: int = 80) -> str:
    text = text or "sin-titulo"
    text = "".join(ch for ch in text if ord(ch) >= 32)
    text = re.sub(r"[:/\\|*?\"<>]", " ", text)
    text = re.sub(r"\s+", "-", text.strip())
    text = re.sub(r"[^A-Za-z0-9\-\._áéíóúÁÉÍÓÚñÑüÜ]", "-", text)
    text = re.sub(r"-{2,}", "-", text)[:max_len].strip(" .-")
    return text or "sin-titulo"