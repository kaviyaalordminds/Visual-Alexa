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


def test_extra_fields_survive_into_the_log_line(monkeypatch, tmp_path):
    """Phase 13 (docs/phase-13-audit.md §5) — real bug: `extra={...}`
    passed to a log call used to be silently discarded by JSONFormatter.
    `app/api/tasks.py`'s own `logger.exception(..., extra={"task_id":
    task_id})` is exactly this real call shape."""
    monkeypatch.setenv("VEYRA_APP_DATA_DIR", str(tmp_path))
    configure_logging("INFO")

    logging.getLogger("test").info(
        "agent.task_run_failed", extra={"task_id": "task-123", "duration": 42}
    )

    log_file = resolve_log_dir() / "local-api.log"
    record = json.loads(log_file.read_text().splitlines()[-1])
    assert record["task_id"] == "task-123"
    assert record["duration"] == 42


def test_extra_fields_that_are_not_json_native_never_crash_logging(monkeypatch, tmp_path):
    monkeypatch.setenv("VEYRA_APP_DATA_DIR", str(tmp_path))
    configure_logging("INFO")

    from veyra_contracts import ErrorCategory

    logging.getLogger("test").info("some event", extra={"error_code": ErrorCategory.TIMEOUT})

    log_file = resolve_log_dir() / "local-api.log"
    record = json.loads(log_file.read_text().splitlines()[-1])
    assert "TIMEOUT" in record["error_code"]


def test_correlation_id_appears_on_log_lines_emitted_while_set(monkeypatch, tmp_path):
    from app.core.logging import get_correlation_id, reset_correlation_id, set_correlation_id

    monkeypatch.setenv("VEYRA_APP_DATA_DIR", str(tmp_path))
    configure_logging("INFO")

    assert get_correlation_id() is None
    token = set_correlation_id("corr-abc")
    try:
        logging.getLogger("test").info("inside the scope")
    finally:
        reset_correlation_id(token)
    logging.getLogger("test").info("outside the scope")

    log_file = resolve_log_dir() / "local-api.log"
    lines = [ln for ln in log_file.read_text().splitlines() if ln]
    records = [json.loads(ln) for ln in lines]
    inside = next(r for r in records if r["message"] == "inside the scope")
    outside = next(r for r in records if r["message"] == "outside the scope")
    assert inside["correlation_id"] == "corr-abc"
    # Restored to the prior value (None), not just left stuck at the last
    # ID ever set — proves reset_correlation_id actually restores scope
    # rather than merely clearing it.
    assert outside["correlation_id"] is None
    assert get_correlation_id() is None


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
