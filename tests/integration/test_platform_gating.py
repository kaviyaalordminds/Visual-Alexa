"""docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2 — on this (Linux) host,
every Windows-only tool must fail honestly with PLATFORM_NOT_SUPPORTED,
never crash, silently no-op, or fabricate a success result.
"""

import pytest

_WINDOWS_ONLY_SAFE_TOOLS = [
    "application.list_running",
    "window.list",
    "window.get_active",
    "ui.find",
]


@pytest.mark.parametrize("tool_id", _WINDOWS_ONLY_SAFE_TOOLS)
async def test_windows_only_tools_report_platform_not_supported(client, tool_id):
    resp = await client.post(f"/tools/{tool_id}/invoke", json={"arguments": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PLATFORM_NOT_SUPPORTED"


async def test_filesystem_and_screen_tools_are_not_platform_gated(client):
    """Sanity check that the platform gate is scoped correctly — it must
    not accidentally catch the genuinely cross-platform tools too."""
    resp = await client.get("/tools")
    tool_ids = {t["id"] for t in resp.json()}
    assert "filesystem.search" in tool_ids
    assert "screen.capture" in tool_ids
