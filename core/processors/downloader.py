# --- filepath: video_narrative_processor/core/processors/downloader.py
from pathlib import Path

from core.processors.base import VideoDownloader
from infrastructure.external.ytdlp_wrapper import YtDlpDownloader

class DefaultDownloader(VideoDownloader):
    def __init__(self):
        self.impl = YtDlpDownloader()

    def download(self, url: str, out_dir: Path):
        return self.impl.download(url, out_dir)