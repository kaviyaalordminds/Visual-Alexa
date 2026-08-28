"""Structured logging foundation. Every log record can carry a
correlation_id so a task/tool-call chain is traceable end-to-end — see
docs/security/06-AUDIT-LOGGING.md and product brief §38 (Observability).
"""

from __future__ import annotations

import contextvars
import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.paths import resolve_app_data_dir

# Phase 10 P1-4 (docs/phase-10/PRODUCTION-AUDIT.md — "no log file or
# rotation... a packaged app with no attached console would have its
# logs simply vanish"). 10 MiB x 5 backups is a deliberately modest cap —
# Part 26: "Do not allow logs to grow indefinitely" — for a single-user
# local desktop app, not a high-throughput server.
_LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
_LOG_FILE_BACKUP_COUNT = 5

_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(correlation_id: str | None) -> None:
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> str | None:
    return _correlation_id_var.get()


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def resolve_log_dir() -> Path:
    """Same app-data location every other piece of mutable VEYRA state
    uses (`app/core/paths.py`) — never inside the install/source
    directory, and honored by `VEYRA_APP_DATA_DIR` the same way."""
    return resolve_app_data_dir() / "logs"


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JSONFormatter())
    root.addHandler(stdout_handler)

    # A packaged, double-clicked app has no attached console — stdout
    # goes nowhere. This is the only durable record of what happened,
    # so a failure to even create it must not crash startup: fall back
    # to stdout-only and say why, rather than taking the whole app down
    # over a logs directory that couldn't be created.
    try:
        log_dir = resolve_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "local-api.log",
            maxBytes=_LOG_FILE_MAX_BYTES,
            backupCount=_LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        root.addHandler(file_handler)
    except OSError:
        root.warning("[VEYRA] Could not open a log file — logging to stdout only.")
