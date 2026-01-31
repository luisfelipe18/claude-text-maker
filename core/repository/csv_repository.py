# --- filepath: video_narrative_processor/core/repository/csv_repository.py
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
from core.models.narrative import VideoNarrative
from core.models.enums import ProcessingStatus, Platform
from core.repository.base import RepositoryProtocol

_DEF_FIELDS = [
    "id",
    "user_id",
    "seq",
    "url",
    "platform",
    "status",
    "title",
    "word_count",
    "video_s3_url",
    "transcript_path",
    "document_path",
    "created_at",
    "completed_at"
]


def _to_serializable(d):
    out = {}
    for k, v in asdict(d).items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


class CSVNarrativeRepository(RepositoryProtocol):
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        if not csv_path.exists():
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=_DEF_FIELDS)
                w.writeheader()

    def save(self, item: VideoNarrative) -> None:
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_DEF_FIELDS)
            w.writerow(_to_serializable(item))

    def update(self, item: VideoNarrative) -> None:
        rows = []
        with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r["id"] == item.id:
                r.update({k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in asdict(item).items()})
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader(); w.writerows(rows)

    def list(self, **filters) -> Iterable[VideoNarrative]:
        with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ok = True
                for k, v in filters.items():
                    if v is None: continue
                    if str(r.get(k)) != str(v): ok = False; break
                if ok:
                    yield VideoNarrative(
                        id=r["id"],
                        user_id=r["user_id"],
                        url=r["url"],
                        platform=Platform(r["platform"]) if r.get("platform") else Platform.UNKNOWN,
                        seq=int(r.get("seq") or 0),
                        status=ProcessingStatus(r["status"]),
                        title=r.get("title") or None,
                        word_count=int(r["word_count"]) if r.get("word_count") else None,
                        video_s3_url=r.get("video_s3_url") or None,
                        transcript_path=Path(r["transcript_path"]) if r.get("transcript_path") else None,
                        document_path=Path(r["document_path"]) if r.get("document_path") else None,
                        created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.now(ZoneInfo("America/Lima")),
                        completed_at=datetime.fromisoformat(r["completed_at"]) if r.get("completed_at") else None,
                    )

    def get(self, item_id: str) -> VideoNarrative | None:
        """Obtiene un registro específico por ID."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["id"] == item_id:
                    return VideoNarrative(
                        id=r["id"],
                        user_id=r["user_id"],
                        url=r["url"],
                        platform=Platform(r["platform"]) if r.get("platform") else Platform.UNKNOWN,
                        seq=int(r.get("seq") or 0),
                        status=ProcessingStatus(r["status"]),
                        title=r.get("title") or None,
                        word_count=int(r["word_count"]) if r.get("word_count") else None,
                        video_s3_url=r.get("video_s3_url") or None,
                        transcript_path=Path(r["transcript_path"]) if r.get("transcript_path") else None,
                        document_path=Path(r["document_path"]) if r.get("document_path") else None,
                        created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.now(ZoneInfo("America/Lima")),
                        completed_at=datetime.fromisoformat(r["completed_at"]) if r.get("completed_at") else None,
                    )
        return None

    def delete(self, item_id: str) -> None:
        """Elimina el registro por ID del CSV."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows = [r for r in rows if r.get("id") != item_id]
        if rows:
            fieldnames = rows[0].keys()
        else:
            fieldnames = _DEF_FIELDS
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    def delete_all_by_user(self, user_id: str) -> int:
        """Elimina todos los registros de un usuario del CSV. Retorna cantidad eliminada."""
        with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        original_count = len(rows)
        rows = [r for r in rows if r.get("user_id") != user_id]
        deleted_count = original_count - len(rows)

        if rows:
            fieldnames = rows[0].keys()
        else:
            fieldnames = _DEF_FIELDS

        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        return deleted_count

