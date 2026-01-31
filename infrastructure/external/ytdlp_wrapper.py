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
            "format": self.format,
            # Opciones para solucionar HTTP 403
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Sec-Fetch-Mode": "navigate",
            },
            "extractor_retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": True,
            "ignoreerrors": False,
            "no_warnings": False,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                ydl.download([url])
                fp = Path(ydl.prepare_filename(info))
                return VideoFile(local_path=fp)
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "403" in error_msg or "Forbidden" in error_msg:
                raise DownloadError(f"Error 403: El sitio bloqueó la descarga. Posibles causas:\n"
                                  f"1. Video privado o restringido\n"
                                  f"2. Requiere inicio de sesión\n"
                                  f"3. Protección anti-bot activa\n"
                                  f"Sugerencia: Intenta actualizar yt-dlp con: pip install -U yt-dlp")
            raise DownloadError(error_msg)
        except Exception as e:
            raise DownloadError(str(e))
