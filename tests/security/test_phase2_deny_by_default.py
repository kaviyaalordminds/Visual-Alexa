"""docs/phase-2 §7, §19, §32 TEST 10/12 — filesystem.delete,
process.terminate, and any generic shell/command-execution tool must not
exist at all. Not disabled — absent."""

import pytest

_MUST_NOT_EXIST = [
    "filesystem.delete",
    "process.terminate",
    "process.kill",
    "system.execute",
    "system.run_command",
    "system.run_shell",
    "system.run_powershell",
]


@pytest.mark.parametrize("tool_id", _MUST_NOT_EXIST)
async def test_dangerous_tool_is_not_registered(client, tool_id):
    resp = await client.get(f"/tools/{tool_id}")
    assert resp.status_code == 404

    invoke_resp = await client.post(f"/tools/{tool_id}/invoke", json={"arguments": {}})
    assert invoke_resp.status_code == 404


async def test_no_registered_tool_accepts_a_free_form_shell_command_argument(client):
    """Defense in depth: even if a future tool were added, no *current*
    tool's schema names a free-form 'command' field."""
    resp = await client.get("/tools")
    for tool in resp.json():
        schema = tool["input_schema"]
        properties = schema.get("properties", {})
        assert "command" not in properties, f"{tool['id']} exposes a raw 'command' argument"
        assert "shell_command" not in properties


async def test_computer_control_disabled_by_default_blocks_every_phase2_tool(client):
    """docs/security/05-DATA-PROTECTION.md §3 — 'off by default, no
    exceptions' applies to computer control as a whole, not just screen
    capture. The test fixture normally flips this on for convenience
    (tests/conftest.py); this test explicitly restores the real seeded
    default and proves every Phase 2 tool honors it.

    screen.capture is MODERATE-tier and needs a PermissionGrant to even
    reach the executor where this gate lives — granted first so the test
    proves the computer_control gate specifically, not just "no grant."
    """
    grant_resp = await client.post(
        "/permissions",
        json={"tool_id": "screen.capture", "risk_level": "MODERATE", "scope": "ALLOW_SESSION"},
    )
    assert grant_resp.status_code == 201

    resp = await client.patch("/settings/computer_control.enabled", json={"value": False})
    assert resp.status_code == 200

    for tool_id, args in [
        ("filesystem.search", {"directory": "/tmp"}),
        ("application.list_running", {}),
        ("window.list", {}),
        ("screen.capture", {}),
    ]:
        invoke_resp = await client.post(f"/tools/{tool_id}/invoke", json={"arguments": args})
        body = invoke_resp.json()
        assert body["status"] == "FAILURE", f"{tool_id} should be blocked"
        assert body["error"]["code"] == "PERMISSION_DENIED"
        assert "computer_control.enabled" in body["error"]["message"]
