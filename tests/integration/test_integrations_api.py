"""End-to-end integration lifecycle through the real HTTP API — the same
ToolRegistry/PolicyEngine/execute_tool_call/CredentialManager chain any
future real integration will go through. docs/phase-7/
INTEGRATION-ARCHITECTURE.md.
"""

from __future__ import annotations


async def test_reference_integration_starts_connect_required(client):
    resp = await client.get("/integrations")
    assert resp.status_code == 200
    by_id = {i["id"]: i for i in resp.json()}
    assert "reference" in by_id
    assert by_id["reference"]["state"] == "CONNECT_REQUIRED"
    assert by_id["reference"]["connected"] is False


async def test_echo_tool_not_registered_before_connecting(client):
    resp = await client.get("/tools")
    tool_ids = [t["id"] for t in resp.json()]
    assert "reference.echo" not in tool_ids


async def test_invoking_before_connecting_is_unknown_tool(client):
    resp = await client.post("/tools/reference.echo/invoke", json={"arguments": {"text": "hi"}})
    assert resp.status_code == 404


async def test_connect_registers_the_tool_and_it_actually_works(client):
    resp = await client.post("/integrations/reference/connect", json={"secret": "test-api-key"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "CONNECTED"
    assert body["connected"] is True

    tool_ids = [t["id"] for t in (await client.get("/tools")).json()]
    assert "reference.echo" in tool_ids

    invoke = await client.post(
        "/tools/reference.echo/invoke", json={"arguments": {"text": "hello there"}}
    )
    assert invoke.status_code == 200
    result = invoke.json()
    assert result["status"] == "SUCCESS"
    assert result["output"]["echo"] == "hello there"


async def test_connect_unknown_integration_is_404(client):
    resp = await client.post("/integrations/does-not-exist/connect", json={"secret": "x"})
    assert resp.status_code == 404


async def test_disconnect_without_connecting_is_409(client):
    resp = await client.post("/integrations/reference/disconnect")
    assert resp.status_code == 409


async def test_disconnect_revokes_credential_and_unregisters_the_tool(client):
    await client.post("/integrations/reference/connect", json={"secret": "test-api-key"})
    resp = await client.post("/integrations/reference/disconnect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "DISCONNECTED"
    assert body["connected"] is False

    tool_ids = [t["id"] for t in (await client.get("/tools")).json()]
    assert "reference.echo" not in tool_ids

    invoke = await client.post("/tools/reference.echo/invoke", json={"arguments": {"text": "hi"}})
    assert invoke.status_code == 404


async def test_health_check_reports_connected_while_credential_is_valid(client):
    await client.post("/integrations/reference/connect", json={"secret": "test-api-key"})
    resp = await client.post("/integrations/reference/health-check")
    assert resp.status_code == 200
    assert resp.json()["state"] == "CONNECTED"
    assert resp.json()["last_health_check_at"] is not None


async def test_health_check_on_a_never_connected_integration_is_unavailable_semantics(client):
    """docs/phase-7 §168-style honesty — nothing to check, no fabricated
    'healthy' state."""
    resp = await client.post("/integrations/reference/health-check")
    assert resp.status_code == 200
    assert resp.json()["state"] == "CONNECT_REQUIRED"


async def test_reconnecting_rotates_the_credential_and_revokes_the_old_one(client):
    """A stale executor built from the first connection's ref must never
    keep working after a fresh connect() — even though this endpoint is
    named 'connect', re-calling it on an already-connected integration is
    a real rotation, not a silent extra grant."""
    from app.db.session import SessionLocal
    from app.services.credential_manager import credential_manager
    from app.services.integration_registry import integration_registry

    await client.post("/integrations/reference/connect", json={"secret": "first-secret"})
    async with SessionLocal() as session:
        first_row = await integration_registry.get_row(session, "reference")
        first_ref = first_row.credentials_ref

    await client.post("/integrations/reference/connect", json={"secret": "second-secret"})
    assert credential_manager.retrieve_credential(first_ref) is None

    invoke = await client.post("/tools/reference.echo/invoke", json={"arguments": {"text": "hi"}})
    assert invoke.status_code == 200
    assert invoke.json()["status"] == "SUCCESS"
