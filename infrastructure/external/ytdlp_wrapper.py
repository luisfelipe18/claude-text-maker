# --- filepath: video_narrative_processor/infrastructure/external/ytdlp_wrapper.py
from pathlib import Path

import yt_dlp

from core.models.artifacts import VideoFile
from utils.exceptions import DownloadError
from core.processors.base import VideoDownloader

class YtDlpDownloader(VideoDownloader):
    def __init__(self, format: str = "mp4/best"):
        self.format = format

    def download(self, url: str, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        template = str(out_dir / "video_%(id)s.%(ext)s")
        opts = {
            "outtmpl": template,
            "noplaylist": True,
            "format": self.format
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                ydl.download([url])
                fp = Path(ydl.prepare_filename(info))
                return VideoFile(local_path=fp)
        except Exception as e:
            raise DownloadError(str(e))
