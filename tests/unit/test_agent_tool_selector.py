"""docs/phase-4/TOOL-SELECTION.md — brief §16/§77: never allow the model
to invent a tool."""

from __future__ import annotations

import pytest
from app.services.agent.tool_selector import ToolSelector, UnknownToolSelectedError
from app.services.tool_registry import ToolRegistry
from veyra_contracts import RiskLevel, ToolCategory, ToolDefinition


def _registry_with_one_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            id="filesystem.search",
            name="Search",
            description="fake",
            category=ToolCategory.FILESYSTEM,
            input_schema={},
            output_schema={},
            risk_level=RiskLevel.SAFE,
            required_permission="filesystem.search",
        ),
        object(),
    )
    return registry


def test_selecting_a_registered_tool_returns_its_definition():
    selector = ToolSelector(_registry_with_one_tool())
    definition = selector.select("filesystem.search")
    assert definition.id == "filesystem.search"


def test_selecting_a_hallucinated_tool_is_rejected():
    selector = ToolSelector(_registry_with_one_tool())
    with pytest.raises(UnknownToolSelectedError) as exc_info:
        selector.select("teleport_to_file")
    assert exc_info.value.tool_id == "teleport_to_file"


def test_exists_is_a_non_raising_check():
    selector = ToolSelector(_registry_with_one_tool())
    assert selector.exists("filesystem.search") is True
    assert selector.exists("teleport_to_file") is False
