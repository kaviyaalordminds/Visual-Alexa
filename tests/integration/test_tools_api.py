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


async def test_list_tools_query_narrows_the_real_registry(client):
    """docs/phase-7/TOOL-DISCOVERY.md — against the real 50-tool registry,
    not a fake catalog."""
    resp = await client.get("/tools", params={"query": "search"})
    assert resp.status_code == 200
    tool_ids = [t["id"] for t in resp.json()]
    assert "filesystem.search" in tool_ids
    assert len(tool_ids) < len((await client.get("/tools")).json())


async def test_list_tools_query_and_category_combine(client):
    resp = await client.get("/tools", params={"query": "search", "category": "windows"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_disabled_tool_never_executes_even_though_still_listed(client):
    """docs/phase-7/TOOL-REGISTRY.md — disable() withholds execution
    without unregistering; the tool stays discoverable."""
    from app.services.tool_registry import tool_registry

    tool_registry.disable("system.get_status")
    try:
        listed = [t["id"] for t in (await client.get("/tools")).json()]
        assert "system.get_status" in listed

        resp = await client.post("/tools/system.get_status/invoke", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "FAILURE"
        assert body["error"]["code"] == "TOOL_DISABLED"
    finally:
        tool_registry.enable("system.get_status")
