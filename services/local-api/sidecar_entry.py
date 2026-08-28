"""PyInstaller entry point for the `veyra-local-api` desktop sidecar.
docs/phase-10/ARCHITECTURE-AUDIT.md §1 (P0-1); built by
scripts/build-backend-sidecar.py, spawned by
apps/desktop/src-tauri/src/lib.rs in a release build.

Not a development entry point — `scripts/dev-backend.bat` and the
documented `uvicorn app.main:app` command are unchanged and remain the
normal way to run the Local API from source. This script exists only
because PyInstaller needs a plain Python script (not a `python -m
uvicorn ...` CLI invocation) to freeze, and because the sidecar has no
terminal to attach `--reload`/interactive output to — it runs headless,
started and stopped entirely by the desktop shell.
"""

from __future__ import annotations

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    # host/port are never overridden here — this must always agree with
    # the same loopback-only default (docs/security/03-THREAT-MODEL.md
    # §5) every other entry point uses; a sidecar binding somewhere the
    # desktop shell doesn't expect would just look like "Local API
    # unreachable" to the frontend, not a security improvement.
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, log_config=None)


if __name__ == "__main__":
    main()
