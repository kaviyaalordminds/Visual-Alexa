"""docs/architecture/04-TOOL-ARCHITECTURE.md end-to-end through the API."""


async def test_list_tools_includes_the_phase1_demo_tool(client):
    resp = await client.get("/tools")
    assert resp.status_code == 200
    tool_ids = [t["id"] for t in resp.json()]
    assert "system.get_status" in tool_ids


async def test_get_unknown_tool_is_404(client):
    resp = await client.get("/tools/does.not.exist")
    assert resp.status_code == 404


async def test_invoke_safe_tool_succeeds_and_returns_settings(client):
    resp = await client.post("/tools/system.get_status/invoke", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["output"]["microphone.enabled"] is False
    assert body["output"]["security.active"] is True


async def test_invoke_unknown_tool_is_404(client):
    resp = await client.post("/tools/does.not.exist/invoke", json={})
    assert resp.status_code == 404
