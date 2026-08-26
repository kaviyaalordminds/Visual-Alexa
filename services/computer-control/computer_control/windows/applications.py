"""Real Windows ApplicationBackend. NOT executable/testable in this Linux
development environment — see computer_control.windows package docstring
and docs/phase-2/APPLICATION-CONTROL.md.

Launching uses `subprocess.Popen` with a list argv and `shell=False`
(the default) — never a shell string, never `os.system`. This is the one
intentional, reviewed subprocess call site in the whole codebase; see
docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §5 and
tests/security/test_subprocess_argv_safety.py.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import psutil

from computer_control.core.models import ApplicationInfo


class WindowsApplicationBackend:
    async def list_running(self) -> list[ApplicationInfo]:
        results: list[ApplicationInfo] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                results.append(
                    ApplicationInfo(
                        name=proc.info["name"] or "",
                        process_id=proc.info["pid"],
                        state="running",
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return results

    async def find(self, query: str) -> list[ApplicationInfo]:
        query_lower = query.lower()
        running = await self.list_running()
        return [app for app in running if query_lower in app.name.lower()]

    async def launch(self, executable_path: str, args: list[str]) -> ApplicationInfo:
        """`executable_path` must already have been resolved and validated
        by the ApplicationRegistry (computer_control.registry) before this
        is called — this backend never receives an unvalidated,
        caller-supplied path. See docs/phase-2/APPLICATION-CONTROL.md."""
        resolved = Path(executable_path)
        if not resolved.is_file():
            raise FileNotFoundError(f"'{executable_path}' does not exist.")
        process = subprocess.Popen([str(resolved), *args], shell=False)
        return ApplicationInfo(name=resolved.stem, process_id=process.pid, state="running")

    async def focus(self, process_id: int) -> bool:
        try:
            import pywinauto
        except ImportError:
            return False
        try:
            app = pywinauto.Application(backend="uia").connect(process=process_id)
            app.top_window().set_focus()
            return True
        except Exception:
            return False

    async def is_running(self, process_id: int) -> bool:
        return psutil.pid_exists(process_id)

    async def close(self, process_id: int) -> bool:
        """A graceful, application-level close (equivalent to clicking the
        window's close button) — deliberately NOT process termination.
        docs/phase-2 §6.5: arbitrary process termination is out of scope
        for Phase 2; this method never calls Process.kill()/terminate()."""
        try:
            import pywinauto
        except ImportError:
            return False
        try:
            app = pywinauto.Application(backend="uia").connect(process=process_id)
            app.top_window().close()
            return True
        except Exception:
            return False
