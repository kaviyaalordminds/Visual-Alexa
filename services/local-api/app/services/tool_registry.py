"""In-process Tool Registry + Executor protocol.
docs/architecture/04-TOOL-ARCHITECTURE.md.

CLAUDE.md: 'Every tool must be registered via ToolRegistry.register() with
a risk_level and required_permission; unregistered tools cannot execute.'
"""

from __future__ import annotations

from typing import Protocol

from veyra_contracts import ToolCallRequest, ToolCategory, ToolDefinition, ToolResult


class ToolExecutor(Protocol):
    async def execute(self, call: ToolCallRequest) -> ToolResult: ...


class ToolRegistrationError(ValueError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._executors: dict[str, ToolExecutor] = {}
        # Phase 7 (docs/phase-7/TOOL-REGISTRY.md) — enable/disable a
        # single registered tool without touching its whole owning
        # integration/plugin. Absent from this dict means enabled
        # (matches every one of the 50 tools registered before this
        # phase, none of which ever called `disable`).
        self._disabled: set[str] = set()

    def register(self, definition: ToolDefinition, executor: ToolExecutor) -> None:
        if not definition.risk_level:
            raise ToolRegistrationError(f"Tool {definition.id} is missing risk_level.")
        if not definition.required_permission:
            raise ToolRegistrationError(f"Tool {definition.id} is missing required_permission.")
        self._definitions[definition.id] = definition
        self._executors[definition.id] = executor

    def unregister(self, tool_id: str) -> None:
        """docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md §3.1/3.6 —
        integration disconnect and plugin disable/remove both need this;
        no-op if the tool was never registered."""
        self._definitions.pop(tool_id, None)
        self._executors.pop(tool_id, None)
        self._disabled.discard(tool_id)

    def get(self, tool_id: str) -> ToolDefinition | None:
        return self._definitions.get(tool_id)

    def get_executor(self, tool_id: str) -> ToolExecutor | None:
        return self._executors.get(tool_id)

    def list(self, category: ToolCategory | None = None) -> list[ToolDefinition]:
        values = list(self._definitions.values())
        if category is not None:
            values = [d for d in values if d.category == category]
        return values

    def disable(self, tool_id: str) -> None:
        """A disabled tool stays registered (still discoverable/listed)
        but `execute_tool_call` refuses to run it — see
        `app/services/tool_execution.py`. Distinct from `unregister`:
        temporarily withholding a tool a user disabled in Settings vs.
        permanently removing one whose owning integration disconnected."""
        if tool_id in self._definitions:
            self._disabled.add(tool_id)

    def enable(self, tool_id: str) -> None:
        self._disabled.discard(tool_id)

    def is_enabled(self, tool_id: str) -> bool:
        return tool_id not in self._disabled


tool_registry = ToolRegistry()
