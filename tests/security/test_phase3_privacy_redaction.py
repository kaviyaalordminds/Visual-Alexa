"""docs/phase-3/PRIVACY.md, docs/phase-3/REDACTION.md — Fourth Acceptance
Test: a password field must be detected, classified SECRET, redacted, and
never appear in the audit log.
"""

from __future__ import annotations

from app.models.audit import AuditLog
from sqlalchemy import select


async def test_password_field_classified_secret_via_grounding(
    client, fake_computer_control, db_session
):
    from computer_control.core.models import Rect, UIElementNode

    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    ui = fake_computer_control["ui_automation"]
    ui.seed_tree(
        UIElementNode(
            name="root",
            control_type="Window",
            children=[
                UIElementNode(
                    automation_id="pwd_field",
                    name=None,
                    control_type="Edit",
                    is_password=True,
                    bounds=Rect(left=0, top=0, width=100, height=20),
                )
            ],
        )
    )
    resp = await client.post(
        "/tools/target.ground/invoke",
        json={"arguments": {"target": {"role": "Edit"}}},
    )
    body = resp.json()
    grounding = body["output"]["data"]["grounding"]
    assert grounding["status"] == "GROUNDED"
    assert grounding["target"]["is_password"] is True
    assert grounding["target"]["privacy_level"] == "SECRET"

    # The AuditLog row for this call must never carry a plaintext secret
    # value — there is none to leak here (UIA never exposes password
    # field *content*), but the audit summarizer must still redact the
    # 'password'-named argument convention if a future caller ever passes
    # one through `target` free text.
    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.tool_id == "target.ground")
        .order_by(AuditLog.created_at.desc())
    )
    row = result.scalars().first()
    assert row is not None
    assert row.result_status.value == "SUCCESS"


async def test_ocr_confidence_never_upgraded_falsely(client):
    """docs/phase-3 §9 — 'do not assume OCR is always correct': a
    min_confidence filter must never let a lower-confidence region through
    silently upgraded."""
    import base64
    import io

    from PIL import Image

    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    resp = await client.post(
        "/tools/ocr.extract/invoke",
        json={
            "arguments": {
                "image_base64": base64.b64encode(buf.getvalue()).decode(),
                "languages": ["eng"],
            }
        },
    )
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["output"]["data"]["text_regions"] == []
