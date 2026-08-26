"""Resolves the filesystem engine's allowed roots for this deployment.
docs/phase-2/FILESYSTEM-CONTROL.md §7.2.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from computer_control.filesystem import PathPolicy, default_policy
from computer_control.filesystem.path_policy import POSIX_PROTECTED_PATTERNS

from app.core.config import Settings


def _is_protected_on_posix(path: Path) -> bool:
    normalized = str(path)
    return any(re.match(pattern, normalized) for pattern in POSIX_PROTECTED_PATTERNS)


def resolve_allowed_roots(settings: Settings) -> list[Path]:
    if settings.filesystem_allowed_roots:
        return [Path(root).expanduser() for root in settings.filesystem_allowed_roots]

    home = Path.home()
    if sys.platform == "win32":
        # docs/phase-2 §3, §7.2 — the ordinary user-writable locations,
        # never the whole filesystem or a system directory.
        candidates = [home / "Documents", home / "Downloads", home / "Desktop"]
    elif _is_protected_on_posix(home):
        # This container runs as root, so Path.home() is '/root' — itself
        # a protected system location (POSIX_PROTECTED_PATTERNS), so a
        # workspace nested under it would always be denied. Fall back to
        # an unambiguously separate location rather than silently
        # widening the protected-path allowlist to accommodate this one
        # environment. See docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2.
        candidates = [Path("/tmp/veyra_workspace")]
    else:
        # This development/CI environment has no Documents/Downloads —
        # see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2. A single,
        # clearly-named workspace directory stands in, created if missing
        # so filesystem tests have somewhere real to run against.
        candidates = [home / "veyra_workspace"]

    for candidate in candidates:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidates


def build_default_policy(settings: Settings) -> PathPolicy:
    return default_policy(resolve_allowed_roots(settings))
