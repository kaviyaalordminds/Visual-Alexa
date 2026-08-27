"""DownloadManager — brief §27-29. Tracks every download the browser
engine observes and enforces the one hard rule around them: a downloaded
file is never automatically executed. docs/phase-8/DOWNLOADS.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.services.browser.adapter import DownloadEvent

# brief §28 — never auto-execute these, or any file with an unrecognized
# extension resembling a script/installer, without explicit high-risk
# authorization (no code path in this phase ever authorizes that; this
# set exists purely so `DownloadManager.is_potentially_dangerous` can
# flag one for the caller/UI, never to gate the download itself — the
# download already happened by the time this is checked).
DANGEROUS_EXTENSIONS: frozenset[str] = frozenset(
    {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".scr", ".com", ".jar", ".sh", ".apk"}
)


@dataclass
class DownloadRecord:
    download_id: str
    session_id: str
    filename: str
    source_url: str
    destination_path: str | None
    status: str  # 'completed' | 'failed'
    error: str | None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_potentially_dangerous(self) -> bool:
        _, ext = os.path.splitext(self.filename.lower())
        return ext in DANGEROUS_EXTENSIONS


class DownloadManager:
    def __init__(self) -> None:
        self._records: dict[str, DownloadRecord] = {}

    def record(self, *, session_id: str, event: DownloadEvent) -> DownloadRecord:
        record = DownloadRecord(
            download_id=str(uuid4()),
            session_id=session_id,
            filename=event.filename,
            source_url=event.source_url,
            destination_path=event.destination_path,
            status="completed" if event.ok else "failed",
            error=event.error,
        )
        self._records[record.download_id] = record
        return record

    def get(self, download_id: str) -> DownloadRecord | None:
        return self._records.get(download_id)

    def list(self, *, session_id: str | None = None) -> list[DownloadRecord]:
        records = list(self._records.values())
        if session_id is not None:
            records = [r for r in records if r.session_id == session_id]
        return sorted(records, key=lambda r: r.started_at, reverse=True)

    def reset(self) -> None:
        """Test-isolation helper — process-global like every other
        registry in this codebase (see mock_iot.reset_mock_ac_state)."""
        self._records.clear()
