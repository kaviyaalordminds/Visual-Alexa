"""The Windows "open with associated application" launcher for
filesystem.open. NOT executable/testable in this Linux development
environment — see computer_control.windows package docstring and
docs/phase-2/FILESYSTEM-CONTROL.md §7.3.

`os.startfile` is the correct, safe Windows mechanism for this: it asks
the shell to open a file with whatever application is associated with its
extension (exactly what double-clicking the file in Explorer does) — it
is not a shell command string and does not go through cmd.exe.
"""

from __future__ import annotations

import os
from pathlib import Path


def open_with_associated_application(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]  # Windows-only stdlib member
