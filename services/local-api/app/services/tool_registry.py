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

    def register(self, definition: ToolDefinition, executor: ToolExecutor) -> None:
        if not definition.risk_level:
            raise ToolRegistrationError(f"Tool {definition.id} is missing risk_level.")
        if not definition.required_permission:
            raise ToolRegistrationError(f"Tool {definition.id} is missing required_permission.")
        self._definitions[definition.id] = definition
        self._executors[definition.id] = executor

    def get(self, tool_id: str) -> ToolDefinition | None:
        return self._definitions.get(tool_id)

    def get_executor(self, tool_id: str) -> ToolExecutor | None:
        return self._executors.get(tool_id)

    def list(self, category: ToolCategory | None = None) -> list[ToolDefinition]:
        values = list(self._definitions.values())
        if category is not None:
            values = [d for d in values if d.category == category]
        return values


tool_registry = ToolRegistry()
