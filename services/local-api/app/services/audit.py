"""Audit logging. docs/security/06-AUDIT-LOGGING.md — every tool call
writes exactly one row, success or failure, every risk tier.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import EvidenceTier, RiskLevel, ToolResultStatus

from app.models.audit import AuditLog

# Fields the summarizer must never include verbatim (docs/security/06 §5).
_SENSITIVE_KEYS = frozenset({"password", "secret", "token", "otp", "credential"})


def summarize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: ("[REDACTED]" if key.lower() in _SENSITIVE_KEYS else value)
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
    return row
