#!/usr/bin/env python3
"""Freezes services/local-api into the Tauri sidecar binary a release
build of the desktop shell spawns. docs/phase-10/ARCHITECTURE-AUDIT.md §1
(P0-1), apps/desktop/src-tauri/src/lib.rs, services/local-api/
sidecar_entry.py.

MUST BE RUN ON WINDOWS, for a Windows build. PyInstaller does not
reliably cross-compile — freezing on Linux/macOS produces a Linux/macOS
binary, not the `.exe` Tauri's sidecar mechanism expects. This script
runs anywhere for convenience (e.g. to sanity-check it starts on a dev
machine of any OS during development of the script itself), but the
*actual* release artifact must come from a Windows run of this script,
ideally in CI on a Windows runner.

Usage (from a Windows machine, inside the project's venv):
    python scripts/build-backend-sidecar.py

Produces:
    apps/desktop/src-tauri/binaries/veyra-local-api-<target-triple>.exe
(a placeholder for the current platform's triple; Tauri's build script
appends this suffix itself when it packages the sidecar — see
`cargo check`'s own error message if this file is missing, which names
the exact triple it expects).

Known gap this script does NOT solve (documented, not silently ignored):
Playwright's Chromium binary is not bundled by PyInstaller — Playwright
downloads it separately into a per-user cache directory
(`playwright install chromium`). A production installer must run that
as a post-install step (or the browser-control subsystem must clearly
report NOT CONFIGURED/DEGRADED until it's done, matching this project's
own "never fake CONNECTED" rule) — this script only freezes the Python
application code.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_API_DIR = _REPO_ROOT / "services" / "local-api"
_DATABASE_DIR = _REPO_ROOT / "database"
_OUTPUT_DIR = _REPO_ROOT / "apps" / "desktop" / "src-tauri" / "binaries"


def _rust_target_triple() -> str:
    # Mirrors what `rustc -vV`'s `host:` line reports — Tauri's sidecar
    # naming convention. Best-effort per-platform default; override by
    # passing --target explicitly if cross-building for a different triple.
    machine = platform.machine().lower()
    arch = "x86_64" if machine in ("x86_64", "amd64") else machine
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-unknown-linux-gnu"


def main() -> int:
    if sys.platform != "win32":
        print(
            "[VEYRA] WARNING: not running on Windows — the produced binary will NOT be "
            "usable as the Windows sidecar. This is fine only for locally sanity-checking "
            "this script itself.",
            file=sys.stderr,
        )

    target_triple = _rust_target_triple()
    binary_name = f"veyra-local-api-{target_triple}"
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[VEYRA] Freezing services/local-api -> {binary_name}")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--name",
            binary_name,
            "--distpath",
            str(_OUTPUT_DIR),
            "--workpath",
            str(_LOCAL_API_DIR / "build"),
            "--specpath",
            str(_LOCAL_API_DIR / "build"),
            # alembic.ini + migrations/ are read at runtime from disk by
            # Alembic's own ScriptDirectory, not imported as Python
            # modules — PyInstaller's static analysis can't find them on
            # its own. app/core/paths.py's resolve_bundled_resource_dir()
            # is what finds this bundle again at runtime (sys._MEIPASS).
            "--add-data",
            f"{_DATABASE_DIR}{';' if sys.platform == 'win32' else ':'}database",
            str(_LOCAL_API_DIR / "sidecar_entry.py"),
        ],
        cwd=str(_LOCAL_API_DIR),
    )
    if result.returncode != 0:
        print("[VEYRA] PyInstaller build FAILED", file=sys.stderr)
        return result.returncode

    print(f"[VEYRA] Sidecar built: {_OUTPUT_DIR / binary_name}")
    print(
        "[VEYRA] Remember: Playwright's Chromium is not bundled — run "
        "'playwright install chromium' as part of the installer or first-run flow."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
