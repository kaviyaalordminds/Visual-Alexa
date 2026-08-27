"""docs/security/04-DEVICE-TRUST.md, docs/security/01-SECURITY-ARCHITECTURE.md
§7 access boundary — IoT/external devices/remote access are DENIED BY
DEFAULT and only reachable after an explicit trust flow. Phase 1 shipped
no adapter for that flow at all; Phase 7
(docs/phase-7/DEVICE-PAIRING.md) builds the real flow (a mock device
only — see test_mock_iot.py), so these tests now assert the *stronger*
version of the same invariant: pairing exists, but nothing is
controllable without genuinely completing every stage in order.
"""


async def test_devices_list_is_empty_by_default(client):
    resp = await client.get("/devices")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_no_generic_command_backdoor_endpoint_exists(client):
    """There is still no way to command a device that bypasses the real
    pairing flow — device control only ever happens through a registered
    tool (iot.mock_ac.*), gated by a real DevicePermission, never a
    generic '/devices/{id}/command'-style shortcut."""
    resp = await client.post("/devices/1/command", json={})
    assert resp.status_code == 404


async def test_pairing_a_device_does_not_make_it_controllable(client):
    """Deny-by-default holds even for a device that completed PAIR:
    nothing is actually controllable until every later stage — including
    a real DevicePermission grant — is reached."""
    pair_resp = await client.post(
        "/devices/pair",
        json={"name": "Test AC", "type": "AC", "protocol": "LOCAL_HTTP"},
    )
    assert pair_resp.status_code == 201
    device = pair_resp.json()
    assert device["trust_status"] == "UNPAIRED"
    assert device["pairing_stage"] == "PAIR"

    invoke = await client.post(
        "/tools/iot.mock_ac.set_power/invoke",
        json={"target": device["id"], "arguments": {"power": True}},
    )
    assert invoke.status_code == 200
    assert invoke.json()["status"] == "FAILURE"
    assert invoke.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_cannot_skip_a_pairing_stage(client):
    pair_resp = await client.post(
        "/devices/pair",
        json={"name": "Test AC", "type": "AC", "protocol": "LOCAL_HTTP"},
    )
    device_id = pair_resp.json()["id"]

    # Skipping straight to AUTHORIZE without IDENTIFY/AUTHENTICATE first.
    resp = await client.post(f"/devices/{device_id}/authorize")
    assert resp.status_code == 400


async def test_pairing_endpoints_404_on_a_nonexistent_device(client):
    for path in (
        "/devices/does-not-exist/identify",
        "/devices/does-not-exist/authorize",
    ):
        resp = await client.post(path, json={})
        assert resp.status_code == 404


async def test_remote_access_setting_defaults_off(client):
    resp = await client.get("/settings")
    settings_by_key = {row["key"]: row["value"] for row in resp.json()}
    assert settings_by_key["remote_access.enabled"] is False
    assert settings_by_key["external_devices.enabled"] is False
    assert settings_by_key["microphone.enabled"] is False
    assert settings_by_key["screen_observation.enabled"] is False


async def test_local_api_binds_loopback_only_by_default():
    from app.core.config import Settings

    assert Settings().host == "127.0.0.1"
