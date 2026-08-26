"""docs/phase-2/SCREEN-CAPTURE.md, docs/security/05-DATA-PROTECTION.md §3.
screen.capture requires BOTH a Policy Engine grant (MODERATE) AND the
`screen_observation.enabled` setting — the setting Phase 1 seeded OFF by
default with nothing checking it until now.
"""

import os

import pytest


async def _grant_screen_capture(client):
    resp = await client.post(
        "/permissions",
        json={"tool_id": "screen.capture", "risk_level": "MODERATE", "scope": "ALLOW_SESSION"},
    )
    assert resp.status_code == 201


async def test_screen_capture_denied_when_observation_setting_is_off_by_default(client):
    await _grant_screen_capture(client)
    resp = await client.post("/tools/screen.capture/invoke", json={"arguments": {}})
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PERMISSION_DENIED"
    assert "screen_observation.enabled" in body["error"]["message"]


async def test_screen_capture_denied_by_policy_engine_even_when_observation_is_enabled(client):
    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    # No PermissionGrant for the MODERATE-tier tool this time.
    resp = await client.post("/tools/screen.capture/invoke", json={"arguments": {}})
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires a real (virtual) X display")
async def test_screen_capture_succeeds_with_both_gates_satisfied(client):
    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    await _grant_screen_capture(client)
    resp = await client.post("/tools/screen.capture/invoke", json={"arguments": {}})
    body = resp.json()
    assert body["status"] == "SUCCESS"
    capture = body["output"]["data"]["capture"]
    assert capture["width"] > 0
    assert capture["height"] > 0
    assert len(capture["image_base64"]) > 0
