"""Desktop <-> API integration, product brief §41 'Desktop communicates
with API' and 'Health endpoint works' acceptance criteria.
"""

import pytest


async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


@pytest.mark.real_computer_control_default
async def test_system_status_defaults_match_status_ui_spec(client):
    """product brief §40 — the exact default status screen values."""
    resp = await client.get("/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["desktop"] == "CONNECTED"
    assert body["local_api"] == "CONNECTED"
    assert body["database"] == "CONNECTED"
    assert body["ai"] == "NOT CONFIGURED"
    assert body["voice"] == "NOT CONFIGURED"
    assert body["vision"] == "NOT CONFIGURED"
    assert body["computer_control"] == "NOT ENABLED"
    assert body["iot"] == "NOT CONNECTED"
    assert body["security"] == "ACTIVE"


async def test_system_status_reports_database_error_truthfully_when_db_is_down(
    client, monkeypatch
):
    """Phase 9 audit P1-2: `database` must be derived from a real, named
    liveness check, not a literal that's only true by accident of an
    earlier query having succeeded. Force that check to fail and confirm
    the endpoint degrades to reporting ERROR (never crashes, never keeps
    claiming CONNECTED)."""

    async def _dead(_session):
        return False

    monkeypatch.setattr("app.api.system._database_is_live", _dead)

    resp = await client.get("/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "ERROR"
    # Still honest about everything else it can't verify without the DB.
    assert body["ai"] == "NOT CONFIGURED"
    assert body["security"] != "ACTIVE"
