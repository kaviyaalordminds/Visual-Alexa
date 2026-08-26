"""docs/security/04-DEVICE-TRUST.md, docs/security/01-SECURITY-ARCHITECTURE.md
§7 access boundary — IoT/external devices/remote access are DENIED BY
DEFAULT and only reachable after an explicit trust flow this phase does not
implement any adapter for.
"""


async def test_devices_list_is_empty_by_default(client):
    resp = await client.get("/devices")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_no_device_pairing_or_command_endpoint_exists(client):
    """No adapter exists in Phase 1, so there must be no way to pair or
    command a device at all yet — not even an unauthenticated one."""
    for path in ("/devices/pair", "/devices/1/command", "/devices/1/authorize"):
        resp = await client.post(path, json={})
        assert resp.status_code == 404, f"{path} should not exist yet"


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
