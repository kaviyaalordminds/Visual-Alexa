"""CLAUDE.md: 'No arbitrary shell execution. No arbitrary PowerShell
execution.' product brief §41 SAFETY acceptance criteria.

This is a static, repo-wide guard: it fails the build the moment anyone
introduces os.system/os.popen/shell=True/PowerShell usage anywhere, or
`subprocess` usage anywhere OTHER than the two specific, reviewed call
sites Phase 2 needs (application.launch and the non-Windows filesystem.open
fallback — see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §5). Those two
call sites are checked far more precisely by
tests/security/test_subprocess_argv_safety.py, which verifies they use a
list argv and shell=False — the property that actually matters — rather
than being exempted from scrutiny.
"""

from __future__ import annotations

import os

_FORBIDDEN_ANYWHERE = (
    "os.system(",
    "os.popen(",
    "shell=True",
    "powershell",
    "PowerShell",
    "Invoke-Expression",
)

# The only two files permitted to call `subprocess` at all in this
# codebase — both reviewed for list-argv/shell=False by
# test_subprocess_argv_safety.py. Any other subprocess usage is forbidden
# by this test, same as before Phase 2.
_SUBPROCESS_ALLOWLIST = {
    os.path.join(
        "services", "computer-control", "computer_control", "windows", "applications.py"
    ),
    os.path.join("services", "computer-control", "computer_control", "launcher.py"),
}

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
        relative = os.path.relpath(path, repo_root)
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for forbidden in _FORBIDDEN_ANYWHERE:
            if forbidden in content:
                offenders.append(f"{path}: contains forbidden pattern '{forbidden}'")
        if "subprocess." in content and relative not in _SUBPROCESS_ALLOWLIST:
            offenders.append(
                f"{path}: uses 'subprocess.' but is not in the reviewed allowlist "
                f"(tests/security/test_no_unrestricted_shell.py:_SUBPROCESS_ALLOWLIST)"
            )
    assert not offenders, "Forbidden execution primitives found:\n" + "\n".join(offenders)
