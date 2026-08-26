"""CLAUDE.md: 'Every tool must be registered via ToolRegistry.register()
with a risk_level and required_permission; unregistered tools cannot
execute.'
"""

import pytest
from app.services.tool_registry import ToolRegistry
from pydantic import ValidationError
from veyra_contracts import RiskLevel, ToolCategory, ToolDefinition


class _NoopExecutor:
    async def execute(self, call):  # pragma: no cover - not exercised
        raise NotImplementedError


def _definition(**overrides) -> ToolDefinition:
    base = {
        "id": "test.tool",
        "name": "Test Tool",
        "description": "A test tool.",
        "category": ToolCategory.SYSTEM,
        "input_schema": {},
        "output_schema": {},
        "risk_level": RiskLevel.SAFE,
        "required_permission": "test.permission",
    }
    base.update(overrides)
    return ToolDefinition(**base)


def test_register_and_get():
    registry = ToolRegistry()
    definition = _definition()
    registry.register(definition, _NoopExecutor())
    assert registry.get("test.tool") is definition
    assert registry.get_executor("test.tool") is not None


def test_unregistered_tool_returns_none():
    registry = ToolRegistry()
    assert registry.get("does.not.exist") is None
    assert registry.get_executor("does.not.exist") is None


def test_list_filters_by_category():
    registry = ToolRegistry()
    registry.register(_definition(id="a", category=ToolCategory.SYSTEM), _NoopExecutor())
    registry.register(_definition(id="b", category=ToolCategory.FILESYSTEM), _NoopExecutor())
    assert [d.id for d in registry.list(category=ToolCategory.FILESYSTEM)] == ["b"]
    assert {d.id for d in registry.list()} == {"a", "b"}


def test_missing_risk_level_rejected_at_the_model_layer():
    # ToolDefinition.risk_level is a required field, so an attempt to
    # construct one without it fails before registration is even possible —
    # this is the strongest form of "cannot execute unregistered/malformed
    # tools" since it's enforced by the type system itself.
    with pytest.raises(ValidationError):
        ToolDefinition(
            id="bad.tool",
            name="Bad",
            description="Missing risk_level",
            category=ToolCategory.SYSTEM,
            input_schema={},
            output_schema={},
            required_permission="x",
        )
