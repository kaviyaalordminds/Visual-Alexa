"""DownloadManager. docs/phase-8/DOWNLOADS.md."""

from __future__ import annotations

from app.services.browser.adapter import DownloadEvent
from app.services.browser.downloads import DownloadManager


def test_record_and_get_a_successful_download():
    dm = DownloadManager()
    record = dm.record(
        session_id="s1",
        event=DownloadEvent(
            filename="report.pdf",
            source_url="https://x/r.pdf",
            destination_path="/tmp/report.pdf",
            size_bytes=100,
            ok=True,
        ),
    )
    fetched = dm.get(record.download_id)
    assert fetched is not None
    assert fetched.status == "completed"


def test_record_failed_download():
    dm = DownloadManager()
    record = dm.record(
        session_id="s1",
        event=DownloadEvent(
            filename="x.pdf",
            source_url="https://x/x.pdf",
            destination_path=None,
            size_bytes=None,
            ok=False,
            error="network error",
        ),
    )
    assert dm.get(record.download_id).status == "failed"


def test_dangerous_extension_flagged():
    dm = DownloadManager()
    record = dm.record(
        session_id="s1",
        event=DownloadEvent(
            filename="installer.exe",
            source_url="https://x/installer.exe",
            destination_path="/tmp/installer.exe",
            size_bytes=1000,
            ok=True,
        ),
    )
    assert record.is_potentially_dangerous


def test_safe_extension_not_flagged():
    dm = DownloadManager()
    record = dm.record(
        session_id="s1",
        event=DownloadEvent(
            filename="report.pdf",
            source_url="https://x/report.pdf",
            destination_path="/tmp/report.pdf",
            size_bytes=1000,
            ok=True,
        ),
    )
    assert not record.is_potentially_dangerous


def test_list_filters_by_session():
    dm = DownloadManager()
    dm.record(session_id="s1", event=DownloadEvent("a.pdf", "u", None, 1, True))
    dm.record(session_id="s2", event=DownloadEvent("b.pdf", "u", None, 1, True))
    assert len(dm.list(session_id="s1")) == 1
    assert len(dm.list()) == 2


def test_reset_clears_all_records():
    dm = DownloadManager()
    dm.record(session_id="s1", event=DownloadEvent("a.pdf", "u", None, 1, True))
    dm.reset()
    assert dm.list() == []
