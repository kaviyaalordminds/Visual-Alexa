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
    """product brief §40 — the exact default status screen values.

    Subsystem activation (docs/subsystem-activation/VISION-STATUS.md):
    `vision` is no longer a blanket NOT CONFIGURED — it genuinely checks
    OCR/screen-capture availability now. This CI/sandbox environment has
    a real `tesseract` binary installed (see tests/unit/test_ocr_engine.py's
    own skip-if-absent guard), so the honest answer here is DEGRADED
    (OCR works, no AI vision model configured), not NOT CONFIGURED — this
    is the health check doing its job, not a regression.
    """
    resp = await client.get("/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["desktop"] == "CONNECTED"
    assert body["local_api"] == "CONNECTED"
    assert body["database"] == "CONNECTED"
    assert body["ai"] == "NOT CONFIGURED"
    assert body["voice"] == "NOT CONFIGURED"
    assert body["vision"] in ("NOT CONFIGURED", "DEGRADED")
    assert body["computer_control"] == "NOT ENABLED"
    # Phase 12 — real browser/memory checks, previously absent fields.
    assert body["browser"] in ("NOT CONNECTED", "NOT CONFIGURED")
    assert body["memory"] == "CONNECTED"
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
    # memory's own check is gated on database_live too — never claims
    # CONNECTED off the back of a DB that's already reported down.
    assert body["memory"] == "ERROR"
