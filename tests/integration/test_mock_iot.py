"""End-to-end mock smart-home device lifecycle through the real HTTP API
— brief §166/§168-169's acceptance tests. docs/phase-7/DEVICE-PAIRING.md,
docs/phase-7/IOT-ARCHITECTURE.md.

No real AC/network/discovery anywhere here — a `DeviceType.AC` row and
two tools (`iot.mock_ac.set_power`/`.set_temperature`) gated by a real
`DevicePermission`, going through the exact same `execute_tool_call`
chain every other tool uses.
"""

from __future__ import annotations

from app.services.mock_iot import get_mock_ac_state


async def _pair(client, name="Living Room AC"):
    resp = await client.post(
        "/devices/pair", json={"name": name, "type": "AC", "protocol": "LOCAL_HTTP"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _invoke_set_power(client, device_id, power):
    return await client.post(
        "/tools/iot.mock_ac.set_power/invoke",
        json={"target": device_id, "arguments": {"power": power}},
    )


async def test_turning_on_ac_with_nothing_paired_fails_honestly_no_scan(client):
    """brief §168 — 'Your AC isn't connected' honesty, never a network
    scan or auto-discovery. There is no device at all here, so the tool
    invocation has no target; the important assertion is what does NOT
    happen: no device row is ever created, no capability is ever
    fabricated."""
    resp = await client.post(
        "/tools/iot.mock_ac.set_power/invoke", json={"arguments": {"power": True}}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert (await client.get("/devices")).json() == []


async def test_full_pairing_flow_reaches_control(client):
    device_id = await _pair(client)

    resp = await client.post(f"/devices/{device_id}/identify")
    assert resp.status_code == 200
    assert resp.json()["pairing_stage"] == "IDENTIFY"
    assert resp.json()["trust_status"] == "PAIRING"

    resp = await client.post(
        f"/devices/{device_id}/authenticate", json={"secret": "device-shared-secret"}
    )
    assert resp.status_code == 200
    assert resp.json()["pairing_stage"] == "AUTHENTICATE"

    resp = await client.post(f"/devices/{device_id}/authorize")
    assert resp.status_code == 200
    assert resp.json()["pairing_stage"] == "AUTHORIZE"

    resp = await client.post(
        f"/devices/{device_id}/register-capabilities",
        json={"capability_keys": ["power", "temperature"]},
    )
    assert resp.status_code == 200
    assert resp.json()["pairing_stage"] == "REGISTER_CAPABILITIES"
    assert resp.json()["trust_status"] == "PAIRED"

    grant = await client.post(
        f"/devices/{device_id}/permissions/grant", json={"capability_key": "power"}
    )
    assert grant.status_code == 201


async def test_acceptance_grant_then_control_then_revoke_then_blocked(client):
    """brief §169 — connect Mock AC, grant AC_CONTROL, 'Turn on AC' is
    allowed; revoke; repeat is blocked."""
    device_id = await _pair(client)
    await client.post(f"/devices/{device_id}/identify")
    await client.post(f"/devices/{device_id}/authenticate", json={"secret": "s"})
    await client.post(f"/devices/{device_id}/authorize")
    await client.post(
        f"/devices/{device_id}/register-capabilities", json={"capability_keys": ["power"]}
    )

    # Not yet granted -> blocked.
    resp = await _invoke_set_power(client, device_id, True)
    assert resp.json()["status"] == "FAILURE"
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"

    await client.post(
        f"/devices/{device_id}/permissions/grant", json={"capability_key": "power"}
    )

    # Granted -> allowed, and the mock device actually reflects it.
    resp = await _invoke_set_power(client, device_id, True)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
    assert get_mock_ac_state(device_id)["power"] is True

    await client.post(
        f"/devices/{device_id}/permissions/revoke", json={"capability_key": "power"}
    )

    # Revoked -> blocked again.
    resp = await _invoke_set_power(client, device_id, False)
    assert resp.json()["status"] == "FAILURE"
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"
    # The last successful command's state is untouched by the blocked one.
    assert get_mock_ac_state(device_id)["power"] is True


async def test_granting_an_unregistered_capability_is_rejected(client):
    device_id = await _pair(client)
    await client.post(f"/devices/{device_id}/identify")
    await client.post(f"/devices/{device_id}/authenticate", json={"secret": "s"})
    await client.post(f"/devices/{device_id}/authorize")
    await client.post(
        f"/devices/{device_id}/register-capabilities", json={"capability_keys": ["power"]}
    )

    resp = await client.post(
        f"/devices/{device_id}/permissions/grant", json={"capability_key": "temperature"}
    )
    assert resp.status_code == 400


async def test_granting_before_capabilities_are_registered_is_rejected(client):
    device_id = await _pair(client)
    await client.post(f"/devices/{device_id}/identify")
    await client.post(f"/devices/{device_id}/authenticate", json={"secret": "s"})
    await client.post(f"/devices/{device_id}/authorize")

    resp = await client.post(
        f"/devices/{device_id}/permissions/grant", json={"capability_key": "power"}
    )
    assert resp.status_code == 400


async def test_expired_permission_is_no_longer_valid(client, monkeypatch):
    device_id = await _pair(client)
    await client.post(f"/devices/{device_id}/identify")
    await client.post(f"/devices/{device_id}/authenticate", json={"secret": "s"})
    await client.post(f"/devices/{device_id}/authorize")
    await client.post(
        f"/devices/{device_id}/register-capabilities", json={"capability_keys": ["power"]}
    )
    await client.post(
        f"/devices/{device_id}/permissions/grant",
        json={"capability_key": "power", "ttl_seconds": -1},
    )

    resp = await _invoke_set_power(client, device_id, True)
    assert resp.json()["status"] == "FAILURE"
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_a_second_capability_can_be_granted_after_control_is_reached(client):
    """CONTROL, once reached, must stay reachable — granting a second
    capability is not a 'stage regression.'"""
    device_id = await _pair(client)
    await client.post(f"/devices/{device_id}/identify")
    await client.post(f"/devices/{device_id}/authenticate", json={"secret": "s"})
    await client.post(f"/devices/{device_id}/authorize")
    await client.post(
        f"/devices/{device_id}/register-capabilities",
        json={"capability_keys": ["power", "temperature"]},
    )
    first = await client.post(
        f"/devices/{device_id}/permissions/grant", json={"capability_key": "power"}
    )
    assert first.status_code == 201
    second = await client.post(
        f"/devices/{device_id}/permissions/grant", json={"capability_key": "temperature"}
    )
    assert second.status_code == 201
