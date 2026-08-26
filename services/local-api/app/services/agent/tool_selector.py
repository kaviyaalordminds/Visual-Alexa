"""ToolSelector — the model may only select from tools that actually
exist in the real Tool Registry. docs/phase-4/TOOL-SELECTION.md.

Argument-shape validation is deliberately NOT duplicated here: every tool
executor already validates its own arguments via a pydantic model
(`app/services/computer_control/*_tools.py`, `app/services/vision/tools.py`)
and `callable_executor` already maps a `ValidationError` to
`TARGET_CONTEXT_REQUIRED`/`VALIDATION_ERROR` — see
docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §1. `ToolSelector`'s one job
is brief §16/§77: reject a tool id that doesn't exist in the registry at
all ('hallucinated tool'), before ever constructing a `ToolCallRequest`
for it.
"""

from __future__ import annotations

from veyra_contracts import ErrorCategory, ToolDefinition

from app.services.tool_registry import ToolRegistry


class UnknownToolSelectedError(LookupError):
    code = ErrorCategory.UNKNOWN_TOOL

    def __init__(self, tool_id: str) -> None:
        super().__init__(
            f"'{tool_id}' is not a registered tool — refusing to plan a "
            "call to a capability that doesn't exist."
        )
        self.tool_id = tool_id


class ToolSelector:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def select(self, tool_id: str) -> ToolDefinition:
        definition = self._registry.get(tool_id)
        if definition is None:
            raise UnknownToolSelectedError(tool_id)
        return definition

    def exists(self, tool_id: str) -> bool:
        return self._registry.get(tool_id) is not None
