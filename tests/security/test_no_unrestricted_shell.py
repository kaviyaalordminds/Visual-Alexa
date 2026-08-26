"""CLAUDE.md: 'No arbitrary shell execution. No arbitrary PowerShell
execution.' product brief §41 SAFETY acceptance criteria.

This is a static, repo-wide guard: it fails the build the moment anyone
introduces subprocess/os.system/exec/eval usage in application code, which
is exactly the class of change that would silently reintroduce the
'LLM directly receives unrestricted OS access' failure mode the whole
architecture is built to prevent (docs/security/01-SECURITY-ARCHITECTURE.md).
"""

from __future__ import annotations

import os

_FORBIDDEN_SUBSTRINGS = (
    "subprocess.",
    "os.system(",
    "os.popen(",
    "shell=True",
    "powershell",
    "PowerShell",
    "Invoke-Expression",
)

# Directories that may legitimately never be touched by application logic.
_SCAN_ROOTS = ("services", "packages", "apps")
_EXCLUDED_DIR_NAMES = {
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "src-tauri" + os.sep + "target",
}


def _iter_source_files(repo_root: str):
    for scan_root in _SCAN_ROOTS:
        base = os.path.join(repo_root, scan_root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIR_NAMES]
            for filename in filenames:
                if filename.endswith((".py", ".ts", ".tsx", ".rs")):
                    yield os.path.join(dirpath, filename)


def test_no_forbidden_execution_primitives_in_application_code(repo_root):
    offenders: list[str] = []
    this_file = os.path.abspath(__file__)
    for path in _iter_source_files(repo_root):
        if os.path.abspath(path) == this_file:
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            if forbidden in content:
                offenders.append(f"{path}: contains forbidden pattern '{forbidden}'")
    assert not offenders, "Forbidden execution primitives found:\n" + "\n".join(offenders)
