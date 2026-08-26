"""docs/security/02-PERMISSION-MODEL.md — grant/list/revoke through the API."""


async def test_grant_list_and_revoke_round_trip(client):
    create_resp = await client.post(
        "/permissions",
        json={
            "tool_id": "filesystem.move",
            "risk_level": "MODERATE",
            "scope": "ALLOW_SESSION",
        },
    )
    assert create_resp.status_code == 201
    grant = create_resp.json()
    assert grant["revoked_at"] is None

    list_resp = await client.get("/permissions")
    assert any(g["id"] == grant["id"] for g in list_resp.json())

    revoke_resp = await client.post(f"/permissions/{grant['id']}/revoke")
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["revoked_at"] is not None


async def test_critical_grant_rejected_by_the_api(client):
    """docs/security/08-SENSITIVE-ACTION-POLICY.md §2 — enforced at the API
    boundary as well as inside the Policy Engine (defense in depth)."""
    resp = await client.post(
        "/permissions",
        json={
            "tool_id": "filesystem.delete",
            "risk_level": "CRITICAL",
            "scope": "ALWAYS_ALLOW",
        },
    )
    assert resp.status_code == 400


async def test_revoking_unknown_grant_is_404(client):
    resp = await client.post("/permissions/does-not-exist/revoke")
    assert resp.status_code == 404
