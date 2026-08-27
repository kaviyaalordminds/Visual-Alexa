"""docs/phase-7/PLUGIN-ARCHITECTURE.md — PluginRegistry default-deny
lifecycle, and brief §170's acceptance test: a mock plugin requesting
filesystem.read + network.access must never receive filesystem.write.
"""

from __future__ import annotations

from time import monotonic

import pytest
from app.services.plugin_registry import (
    IllegalPluginStateError,
    PermissionNotRequestedError,
    PluginRegistry,
    UnknownPluginError,
)
from app.services.tool_registry import ToolRegistry
from veyra_contracts import (
    PluginManifest,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)


class _NoopExecutor:
    async def execute(self, call: ToolCallRequest) -> ToolResult:  # pragma: no cover
        return ToolResult(
            call_id=call.call_id, status=ToolResultStatus.SUCCESS, output={}, duration_ms=0
        )


def _tool(tool_id: str, required_permission: str) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=tool_id,
        description="Mock plugin tool.",
        category=ToolCategory.CUSTOM,
        input_schema={},
        output_schema={},
        risk_level=RiskLevel.SAFE,
        required_permission=required_permission,
    )


def _mock_plugin_manifest() -> PluginManifest:
    """brief §170's own scenario: a plugin *requesting* filesystem.read
    and network.access — deliberately never requesting filesystem.write
    at all, so there is nothing to grant even if a caller tried."""
    return PluginManifest(
        id="mock-plugin",
        name="Mock Plugin",
        version="1.0.0",
        description="A mock plugin for the brief §170 acceptance test.",
        author="test",
        permissions=["filesystem.read", "network.access"],
        tools=["mock_plugin.read_file", "mock_plugin.write_file"],
        entrypoint="mock_plugin:main",
        platforms=["linux", "windows"],
    )


def _mock_plugin_tool_builder():
    return [
        (_tool("mock_plugin.read_file", "filesystem.read"), _NoopExecutor()),
        # Requires a permission the manifest above never even requested —
        # this must never go live, under any circumstance.
        (_tool("mock_plugin.write_file", "filesystem.write"), _NoopExecutor()),
    ]


@pytest.fixture
def registry() -> PluginRegistry:
    return PluginRegistry()


@pytest.fixture
def tool_registry() -> ToolRegistry:
    return ToolRegistry()


async def test_install_always_starts_untrusted_with_nothing_granted(registry, db_session):
    row = await registry.install(db_session, _mock_plugin_manifest())
    assert row.state.value == "UNTRUSTED"
    permissions = await registry.list_permissions(db_session, row.id)
    assert {p.permission for p in permissions} == {"filesystem.read", "network.access"}
    assert all(not p.granted for p in permissions)


async def test_cannot_grant_a_permission_never_requested(registry, db_session):
    row = await registry.install(db_session, _mock_plugin_manifest())
    with pytest.raises(PermissionNotRequestedError):
        await registry.grant(db_session, row.id, "filesystem.write")


async def test_cannot_enable_before_trusted(registry, tool_registry, db_session):
    row = await registry.install(db_session, _mock_plugin_manifest())
    with pytest.raises(IllegalPluginStateError):
        await registry.enable(db_session, tool_registry, row.id)


async def test_acceptance_write_never_becomes_usable_even_when_enabled(
    registry, tool_registry, db_session
):
    """brief §170 — install a mock plugin requesting filesystem.read +
    network.access; expected: it cannot receive filesystem.write unless
    granted (it never can be, since it was never requested)."""
    row = await registry.install(
        db_session, _mock_plugin_manifest(), tool_builder=_mock_plugin_tool_builder
    )
    await registry.grant(db_session, row.id, "filesystem.read")
    await registry.mark_trusted(db_session, row.id)
    await registry.enable(db_session, tool_registry, row.id)

    assert tool_registry.get("mock_plugin.read_file") is not None
    assert tool_registry.get("mock_plugin.write_file") is None


async def test_ungranted_requested_permission_also_never_goes_live(
    registry, tool_registry, db_session
):
    """network.access was requested but this test never grants it — a
    tool requiring it (if the plugin declared one) must stay dark too;
    demonstrated here by leaving filesystem.read ungranted as well."""
    row = await registry.install(
        db_session, _mock_plugin_manifest(), tool_builder=_mock_plugin_tool_builder
    )
    await registry.mark_trusted(db_session, row.id)
    await registry.enable(db_session, tool_registry, row.id)

    assert tool_registry.get("mock_plugin.read_file") is None
    assert tool_registry.get("mock_plugin.write_file") is None


async def test_disable_unregisters_previously_enabled_tools(registry, tool_registry, db_session):
    row = await registry.install(
        db_session, _mock_plugin_manifest(), tool_builder=_mock_plugin_tool_builder
    )
    await registry.grant(db_session, row.id, "filesystem.read")
    await registry.mark_trusted(db_session, row.id)
    await registry.enable(db_session, tool_registry, row.id)
    assert tool_registry.get("mock_plugin.read_file") is not None

    await registry.disable(db_session, tool_registry, row.id)
    assert tool_registry.get("mock_plugin.read_file") is None


async def test_revoking_a_granted_permission_takes_effect_on_next_enable(
    registry, tool_registry, db_session
):
    row = await registry.install(
        db_session, _mock_plugin_manifest(), tool_builder=_mock_plugin_tool_builder
    )
    await registry.grant(db_session, row.id, "filesystem.read")
    await registry.mark_trusted(db_session, row.id)
    await registry.enable(db_session, tool_registry, row.id)
    assert tool_registry.get("mock_plugin.read_file") is not None

    await registry.disable(db_session, tool_registry, row.id)
    await registry.revoke_permission(db_session, row.id, "filesystem.read")
    await registry.enable(db_session, tool_registry, row.id)
    assert tool_registry.get("mock_plugin.read_file") is None


async def test_remove_deletes_the_plugin_and_unregisters_its_tools(
    registry, tool_registry, db_session
):
    row = await registry.install(
        db_session, _mock_plugin_manifest(), tool_builder=_mock_plugin_tool_builder
    )
    await registry.grant(db_session, row.id, "filesystem.read")
    await registry.mark_trusted(db_session, row.id)
    await registry.enable(db_session, tool_registry, row.id)

    await registry.remove(db_session, tool_registry, row.id)
    assert tool_registry.get("mock_plugin.read_file") is None
    with pytest.raises(UnknownPluginError):
        await registry.get(db_session, row.id)


async def test_install_never_executes_or_imports_the_entrypoint(registry, db_session):
    """The manifest's `entrypoint` ('mock_plugin:main') is never a real,
    importable module in this test process — install() must not attempt
    to load or run it (brief §69)."""
    started = monotonic()
    row = await registry.install(db_session, _mock_plugin_manifest())
    assert row.id  # completed without raising ImportError/ModuleNotFoundError
    assert monotonic() - started < 1.0
