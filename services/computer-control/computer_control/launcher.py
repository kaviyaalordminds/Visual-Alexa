"""Resolves the platform-appropriate 'open with associated application'
mechanism for filesystem.open. docs/phase-2/FILESYSTEM-CONTROL.md §7.3.

Windows uses `os.startfile` (computer_control.windows.filesystem_launcher).
Non-Windows hosts (this development environment included) fall back to
`xdg-open`/`open` via a list-argv subprocess call — never a shell string —
so filesystem.open's validation/verification logic is exercisable for
real here too, even though it isn't the production mechanism.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


class NoAssociatedApplicationLauncherError(RuntimeError):
    pass


def _posix_open(path: Path) -> None:
    command = "open" if sys.platform == "darwin" else "xdg-open"
    resolved = shutil.which(command)
    if resolved is None:
        raise NoAssociatedApplicationLauncherError(
            f"No '{command}' available on this host to open '{path}'."
        )
    subprocess.Popen([resolved, str(path)], shell=False)


def default_launcher() -> Callable[[Path], None]:
    if sys.platform == "win32":
        from computer_control.windows.filesystem_launcher import (
            open_with_associated_application,
        )

        return open_with_associated_application
    return _posix_open
