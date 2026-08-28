"""system.ai_health_check / system.voice_health_check — the user-
triggerable diagnostic actions. docs/subsystem-activation/AI-STATUS.md,
VOICE-STATUS.md. Exercised through the real POST /tools/{id}/invoke path
— the same ToolRegistry -> PolicyEngine -> Executor -> AuditLog chokepoint
every other tool uses.
"""

from __future__ import annotations

from app.models.audit import AuditLog
from app.services.subsystem_health import reset_ai_check_cache
from sqlalchemy import select


async def test_ai_health_check_reports_not_configured_by_default(client):
    reset_ai_check_cache()
    resp = await client.post("/tools/system.ai_health_check/invoke", json={})
    assert resp.status_code == 200
    output = resp.json()["output"]
    assert output["configured"] is False
    assert output["reachable"] is False


async def test_ai_health_check_writes_an_audit_row_and_never_leaks_the_api_key(
    client, db_session, monkeypatch
):
    secret = "sk-do-not-leak-this-value"
    fake_settings = type(
        "S",
        (),
        {
            "ai_provider": "openai-compatible",
            "ai_model": "m",
            "ai_api_key": secret,
            "ai_base_url": "https://api.example.invalid/v1",
        },
    )()
    monkeypatch.setattr(
        "app.services.subsystem_diagnostics_tools.get_settings", lambda: fake_settings
    )

    resp = await client.post("/tools/system.ai_health_check/invoke", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert secret not in resp.text
    assert body["output"]["configured"] is True
    # Unreachable host (invalid TLD) — a real network attempt that fails,
    # not a fabricated success.
    assert body["output"]["reachable"] is False

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.tool_id == "system.ai_health_check")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert secret not in str(rows[0].request_payload_summary)
    reset_ai_check_cache()


async def test_voice_health_check_reports_configuration_state(client):
    resp = await client.post("/tools/system.voice_health_check/invoke", json={})
    assert resp.status_code == 200
    output = resp.json()["output"]
    assert output["status"] == "NOT CONFIGURED"
    assert "reason" in output
