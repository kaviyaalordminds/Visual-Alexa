"""docs/phase-7/INTEGRATION-ARCHITECTURE.md §3.2 — reconnect_all_on_startup
is never exercised by the HTTP-level tests (nothing actually restarts the
process mid-test), so it gets its own direct coverage here."""

from __future__ import annotations

from app.services.credential_manager import CredentialManager, FileCredentialStore
from app.services.integration_registry import IntegrationRegistry
from app.services.reference_integration import (
    REFERENCE_ECHO_TOOL_ID,
    REFERENCE_INTEGRATION_ID,
    build_reference_integration_bundle,
)
from app.services.tool_registry import ToolRegistry


def _registry(tmp_path) -> tuple[IntegrationRegistry, CredentialManager]:
    cm = CredentialManager(FileCredentialStore(secret_key="k", path=tmp_path / "c.enc.json"))
    reg = IntegrationRegistry(cm)
    reg.register_definition(build_reference_integration_bundle(cm))
    return reg, cm


def test_list_definitions_includes_registered_bundle(tmp_path):
    reg, _ = _registry(tmp_path)
    ids = [d.id for d in reg.list_definitions()]
    assert REFERENCE_INTEGRATION_ID in ids


def test_get_definition_unknown_returns_none(tmp_path):
    reg, _ = _registry(tmp_path)
    assert reg.get_definition("does-not-exist") is None


async def test_reconnect_all_on_startup_re_registers_a_previously_connected_integration(
    tmp_path, db_session
):
    reg, _cm = _registry(tmp_path)
    tool_registry = ToolRegistry()

    connect_result = await reg.connect(
        db_session, tool_registry, REFERENCE_INTEGRATION_ID, secret="real-secret"
    )
    assert connect_result.success

    # Simulate a process restart: a brand new ToolRegistry with nothing
    # registered, the same DB rows and credential store as before.
    fresh_tool_registry = ToolRegistry()
    assert fresh_tool_registry.get(REFERENCE_ECHO_TOOL_ID) is None

    await reg.reconnect_all_on_startup(db_session, fresh_tool_registry)
    assert fresh_tool_registry.get(REFERENCE_ECHO_TOOL_ID) is not None


async def test_reconnect_all_on_startup_marks_an_invalid_credential_expired(tmp_path, db_session):
    reg, cm = _registry(tmp_path)
    tool_registry = ToolRegistry()
    await reg.connect(db_session, tool_registry, REFERENCE_INTEGRATION_ID, secret="real-secret")

    row = await reg.get_row(db_session, REFERENCE_INTEGRATION_ID)
    assert row is not None
    cm.delete_credential(row.credentials_ref)  # simulate external revocation

    fresh_tool_registry = ToolRegistry()
    await reg.reconnect_all_on_startup(db_session, fresh_tool_registry)

    assert fresh_tool_registry.get(REFERENCE_ECHO_TOOL_ID) is None
    reloaded = await reg.get_row(db_session, REFERENCE_INTEGRATION_ID)
    assert reloaded.connected is False
    assert reloaded.state.value == "EXPIRED"


async def test_reconnect_all_on_startup_skips_never_connected_integrations(tmp_path, db_session):
    reg, _ = _registry(tmp_path)
    tool_registry = ToolRegistry()
    await reg.reconnect_all_on_startup(db_session, tool_registry)
    assert tool_registry.get(REFERENCE_ECHO_TOOL_ID) is None
