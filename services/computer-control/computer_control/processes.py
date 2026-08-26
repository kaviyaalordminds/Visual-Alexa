"""Process inspection backend. Cross-platform via `psutil` — see
docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §4 for why this one part of
the engine is not gated behind sys.platform == 'win32'.

docs/phase-2 §6.5: read-only. No process termination is implemented in
Phase 2 — see docs/roadmap and the Phase 2 report for why.
"""

from __future__ import annotations

import psutil

from computer_control.core.models import ProcessInfo


class PsutilProcessBackend:
    async def list_processes(self) -> list[ProcessInfo]:
        results: list[ProcessInfo] = []
        for proc in psutil.process_iter(["pid", "name", "ppid"]):
            try:
                info = proc.info
                results.append(
                    ProcessInfo(
                        pid=info["pid"],
                        name=info["name"] or "",
                        parent_pid=info.get("ppid"),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # A process can exit between iteration and info access —
                # this is expected and not an error condition.
                continue
        return results

    async def find_process(self, name_query: str) -> list[ProcessInfo]:
        query_lower = name_query.lower()
        all_processes = await self.list_processes()
        return [p for p in all_processes if query_lower in p.name.lower()]
