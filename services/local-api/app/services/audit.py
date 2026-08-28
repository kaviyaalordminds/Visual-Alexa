"""Audit logging. docs/security/06-AUDIT-LOGGING.md — every tool call
writes exactly one row, success or failure, every risk tier.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import EventType, EvidenceTier, RiskLevel, ToolResultStatus

from app.core.event_bus import event_bus
from app.models.audit import AuditLog

# Fields the summarizer must never include verbatim (docs/security/06 §5).
_SENSITIVE_KEYS = frozenset({"password", "secret", "token", "otp", "credential"})

# docs/phase-8/BROWSER-SECURITY.md §129 — 'Audit: "Typed password" NOT:
# actual password.' A generic-shaped tool call (e.g. `browser.type`'s
# `{"query": "Password", "text": "<the actual value>"}`) never puts the
# secret under a recognizably-named key like "password" — the *target
# field's own label* is what's sensitive, and the value sits under an
# unrelated generic key ("text"). Real value here: `app/services/browser/
# tools.py`'s `_SENSITIVE_FIELD_LABELS` reuses this exact set rather than
# duplicating it, so the two checks (refuse to auto-fill vs. never log)
# can never silently drift apart.
SENSITIVE_FIELD_HINTS: frozenset[str] = frozenset(
    {
        "password",
        "passcode",
        "pin",
        "ssn",
        "social security",
        "card number",
        "cvv",
        "cvc",
        "otp",
        "one-time code",
        "security answer",
        "bank account",
        "routing number",
    }
)
# Generic free-text argument keys that, on their own, name nothing
# sensitive — but which redact too when another key in the same payload
# names a sensitive target (see `summarize_payload` below).
_FREEFORM_VALUE_KEYS = frozenset({"text", "value"})


def summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sensitive_context = any(
        key.lower() not in _FREEFORM_VALUE_KEYS
        and isinstance(value, str)
        and any(hint in value.lower() for hint in SENSITIVE_FIELD_HINTS)
        for key, value in payload.items()
    )
    return {
        key: (
            "[REDACTED]"
            if key.lower() in _SENSITIVE_KEYS
            or (sensitive_context and key.lower() in _FREEFORM_VALUE_KEYS)
            else value
        )
        for key, value in payload.items()
    }


async def write_audit_log(
    session: AsyncSession,
    *,
    correlation_id: str,
    user_id: str | None,
    tool_id: str | None,
    action: str,
    target: str | None,
    risk_level: RiskLevel,
    permission_grant_id: str | None,
    request_payload_summary: dict[str, Any],
    result_status: ToolResultStatus,
    error_code: str | None,
    evidence_tier_used: EvidenceTier | None,
    duration_ms: int,
) -> AuditLog:
    row = AuditLog(
        correlation_id=correlation_id,
        user_id=user_id,
        tool_id=tool_id,
        action=action,
        target=target,
        risk_level=risk_level,
        permission_grant_id=permission_grant_id,
        request_payload_summary=summarize_payload(request_payload_summary),
        result_status=result_status,
        error_code=error_code,
        evidence_tier_used=evidence_tier_used,
        duration_ms=duration_ms,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    # Phase 12 — every AuditLog row already goes through this one
    # function (docs/security/06-AUDIT-LOGGING.md); publishing here means
    # a security dashboard can observe audit entries in real time without
    # polling, with no second write path and no risk of drifting from
    # what actually got persisted (the event is built from the same row).
    await event_bus.publish_type(
        EventType.AUDIT_RECORD_CREATED,
        correlation_id,
        {
            "tool_id": tool_id,
            "action": action,
            "risk_level": risk_level.value,
            "result_status": result_status.value,
        },
    )
    return row
