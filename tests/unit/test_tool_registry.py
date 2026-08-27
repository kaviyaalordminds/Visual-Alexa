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


def test_unregister_removes_definition_and_executor():
    registry = ToolRegistry()
    registry.register(_definition(), _NoopExecutor())
    registry.unregister("test.tool")
    assert registry.get("test.tool") is None
    assert registry.get_executor("test.tool") is None


def test_unregister_unknown_tool_is_a_harmless_noop():
    registry = ToolRegistry()
    registry.unregister("does.not.exist")  # must not raise


def test_new_tools_are_enabled_by_default():
    registry = ToolRegistry()
    registry.register(_definition(), _NoopExecutor())
    assert registry.is_enabled("test.tool") is True


def test_disable_then_enable_round_trips():
    registry = ToolRegistry()
    registry.register(_definition(), _NoopExecutor())
    registry.disable("test.tool")
    assert registry.is_enabled("test.tool") is False
    registry.enable("test.tool")
    assert registry.is_enabled("test.tool") is True


def test_disabling_an_unregistered_tool_is_a_harmless_noop():
    registry = ToolRegistry()
    registry.disable("does.not.exist")
    assert registry.is_enabled("does.not.exist") is True


def test_unregister_clears_any_disabled_flag():
    registry = ToolRegistry()
    registry.register(_definition(), _NoopExecutor())
    registry.disable("test.tool")
    registry.unregister("test.tool")
    registry.register(_definition(), _NoopExecutor())
    assert registry.is_enabled("test.tool") is True


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
