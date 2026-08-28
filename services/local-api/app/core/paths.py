"""Where VEYRA's mutable data and bundled resources live — uniformly
across a source checkout, the test suite, and a frozen production build.
docs/phase-10/ARCHITECTURE-AUDIT.md §5-6 (P0-2), Part 35 (app data
directory).

Two genuinely different questions, kept separate:

- `resolve_app_data_dir()` — where VEYRA's *mutable* data (database,
  credentials store, browser downloads) lives. Never inside the
  application's own install/source directory: `C:\\Program Files\\VEYRA\\`
  requires admin rights to write to and isn't multi-user-safe; the
  previous default (anchored to this package's own file location,
  `parents[4]`) put a running app's live data inside whatever directory
  happened to contain the source tree — wrong for an installed app, and
  arguably wrong even for a developer checkout (Part 35: "Do NOT store
  mutable production data inside the source directory").
- `resolve_bundled_resource_dir()` — where VEYRA's own *read-only,
  shipped* resources live (currently: `database/alembic.ini` +
  `database/migrations/`, which Alembic loads from disk at runtime, not
  via a normal Python import — see `app/db/migrate.py`). In a frozen
  build this is PyInstaller's extraction directory; in a source checkout
  it's the repo root, exactly as the pre-Phase-10 code already assumed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True inside the PyInstaller-frozen sidecar built by
    scripts/build-backend-sidecar.py. False in every dev/test/source
    scenario, including this repo's own test suite."""
    return bool(getattr(sys, "frozen", False))


def resolve_app_data_dir() -> Path:
    """`VEYRA_APP_DATA_DIR` overrides this explicitly — used by the test
    suite for per-test isolation (tests/conftest.py), and available for
    any deployment that wants a non-default data location. Otherwise: a
    real, per-user, OS-appropriate directory, matching each platform's own
    convention (Windows `%APPDATA%`, macOS `~/Library/Application
    Support`, Linux XDG `$XDG_DATA_HOME` or `~/.local/share`)."""
    override = os.environ.get("VEYRA_APP_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "VEYRA"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "VEYRA"
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "veyra"


def resolve_bundled_resource_dir() -> Path:
    """Inside a frozen build, PyInstaller's own extraction directory
    (`sys._MEIPASS`) — `scripts/build-backend-sidecar.py` bundles
    `database/` (alembic.ini + migrations/) there as read-only data
    files. In a source checkout (dev, tests, `scripts/dev-backend.bat`),
    the real repo root: `services/local-api/app/core/paths.py` is always
    4 parents above it."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", "."))
    return Path(__file__).resolve().parents[4]
