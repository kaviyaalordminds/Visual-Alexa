"""docs/phase-2 §28 — audit logs for computer-control tools must never
contain typed secret values (passwords, OTPs, API keys, tokens).
"""

from app.models.audit import AuditLog
from sqlalchemy import select


async def _grant(client, tool_id, risk):
    resp = await client.post(
        "/permissions", json={"tool_id": tool_id, "risk_level": risk, "scope": "ALLOW_SESSION"}
    )
    assert resp.status_code == 201


async def test_keyboard_type_audit_row_redacts_a_password_argument(
    client, fake_computer_control, db_session
):
    await _grant(client, "keyboard.type", "SENSITIVE")
    resp = await client.post(
        "/tools/keyboard.type/invoke",
        json={
            "arguments": {
                "target": {"window_title": "Login"},
                "text": "irrelevant-for-this-test",
                "password": "hunter2",
            }
        },
    )
    assert resp.status_code == 200

    result = await db_session.execute(select(AuditLog).where(AuditLog.tool_id == "keyboard.type"))
    rows = result.scalars().all()
    assert len(rows) == 1
    summary = rows[0].request_payload_summary
    assert summary.get("password") == "[REDACTED]"


async def test_every_computer_control_invocation_writes_exactly_one_audit_row(
    client, db_session, fs_sandbox
):
    resp = await client.post(
        "/tools/filesystem.search/invoke", json={"arguments": {"directory": fs_sandbox}}
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.tool_id == "filesystem.search")
    )
    assert len(result.scalars().all()) == 1
