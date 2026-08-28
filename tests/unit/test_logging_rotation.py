"""app.core.logging — Phase 10 P1 (docs/phase-10/PRODUCTION-AUDIT.md):
a packaged app with no attached console must still have a durable log
record, and that record must never grow without bound.
"""

from __future__ import annotations

import json
import logging
import logging.handlers

import pytest
from app.core.logging import configure_logging, resolve_log_dir


@pytest.fixture(autouse=True)
def _restore_root_logger_handlers():
    """configure_logging() replaces the ROOT logger's handlers wholesale
    (by design — see app/db/migrate.py's own comment on why). These
    tests are the only ones that call it directly; restore the prior
    handlers afterward so this file's own logging setup never leaks into
    unrelated tests running later in the same process."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for handler in root.handlers:
        if handler not in original_handlers:
            handler.close()
    root.handlers = original_handlers
    root.setLevel(original_level)


def test_configure_logging_creates_a_rotating_file_handler(monkeypatch, tmp_path):
    monkeypatch.setenv("VEYRA_APP_DATA_DIR", str(tmp_path))
    configure_logging("INFO")

    root = logging.getLogger()
    file_handlers = [
        h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    assert file_handlers[0].maxBytes > 0
    assert file_handlers[0].backupCount > 0


def test_log_records_are_actually_written_to_the_file(monkeypatch, tmp_path):
    monkeypatch.setenv("VEYRA_APP_DATA_DIR", str(tmp_path))
    configure_logging("INFO")

    logging.getLogger("test").info("hello from the test")

    log_file = resolve_log_dir() / "local-api.log"
    assert log_file.exists()
    lines = [ln for ln in log_file.read_text().splitlines() if ln.strip()]
    assert any("hello from the test" in ln for ln in lines)
    # Real structured JSON, not a bare string.
    record = json.loads(lines[-1])
    assert record["level"] == "INFO"
    assert "timestamp" in record


def test_configure_logging_never_raises_if_the_log_dir_cannot_be_created(monkeypatch, tmp_path):
    def _boom(*args, **kwargs):
        raise OSError("permission denied (simulated)")

    monkeypatch.setenv("VEYRA_APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.mkdir", _boom)

    configure_logging("INFO")  # must not raise

    root = logging.getLogger()
    file_handlers = [
        h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert file_handlers == []  # fell back to stdout-only, as documented
