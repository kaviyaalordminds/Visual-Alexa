"""Builds the process-wide `AgentOrchestrator` singleton at startup —
mirrors the `tool_registry`/`application_registry` singleton pattern
already used by Phase 1/2. docs/phase-4/AGENT-ARCHITECTURE.md.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.agent.orchestrator import AgentOrchestrator
from app.services.filesystem_config import resolve_allowed_roots
from app.services.tool_registry import ToolRegistry

_orchestrator: AgentOrchestrator | None = None


def init_orchestrator(registry: ToolRegistry, settings: Settings) -> AgentOrchestrator:
    global _orchestrator
    roots = [str(p) for p in resolve_allowed_roots(settings)]
    _orchestrator = AgentOrchestrator(registry, roots)
    return _orchestrator


def get_orchestrator() -> AgentOrchestrator:
    if _orchestrator is None:
        raise RuntimeError(
            "AgentOrchestrator was not initialized — init_orchestrator() must run "
            "at process startup (see app/main.py)."
        )
    return _orchestrator
