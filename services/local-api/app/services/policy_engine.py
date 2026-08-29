"""Policy Engine — the single enforcement point for every tool call.
docs/security/02-PERMISSION-MODEL.md §3, docs/security/01-SECURITY-ARCHITECTURE.md.

This is the code that makes the security model real rather than aspirational:
it does not trust anything the caller (including the model/planner) claims —
it independently checks stored PermissionGrant rows against the tool's own
registered risk_level.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import PermissionDecision, RiskLevel

from app.models.tool import PermissionGrant as PermissionGrantRow


def _as_aware_utc(value: datetime | None) -> datetime | None:
    """SQLite has no native timezone-aware datetime storage, so values read
    back through SQLAlchemy's SQLite dialect come back naive even though
    they were written as UTC-aware — normalize before comparing."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str
    matched_grant_id: str | None = None


class PolicyEngine:
    async def evaluate(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        tool_id: str,
        risk_level: RiskLevel,
        target: str | None,
    ) -> PolicyDecision:
        # SAFE tools are allowed under the default policy — still policy
        # checked (this code path always runs), just never blocked.
        # docs/architecture/04-TOOL-ARCHITECTURE.md §6.
        if risk_level == RiskLevel.SAFE:
            return PolicyDecision(
                allowed=True,
                requires_confirmation=False,
                reason="SAFE-tier tools are allowed under the default policy.",
            )

        # CRITICAL actions can never be satisfied by a stored grant, no
        # matter how broad (including ALWAYS_ALLOW) — see
        # docs/security/08-SENSITIVE-ACTION-POLICY.md §2.
        if risk_level == RiskLevel.CRITICAL:
            return PolicyDecision(
                allowed=False,
                requires_confirmation=True,
                reason="CRITICAL-risk actions always require fresh, explicit confirmation.",
            )

        now = datetime.now(UTC)
        stmt = select(PermissionGrantRow).where(
            PermissionGrantRow.user_id == user_id,
            PermissionGrantRow.tool_id == tool_id,
            PermissionGrantRow.revoked_at.is_(None),
        )
        result = await session.execute(stmt)
        for grant in result.scalars():
            if grant.target is not None and grant.target != target:
                continue
            expires_at = _as_aware_utc(grant.expires_at)
            if expires_at is not None and expires_at <= now:
                continue
            if grant.scope == PermissionDecision.ALLOW_ONCE:
                # Phase 13 (live-verification finding, docs/phase-13-
                # audit.md) — an ALLOW_ONCE grant was created with the
                # documented intent of authorizing exactly one attempt
                # (see confirmation_actions.py's own comment: "single-
                # use... never a standing ALWAYS_ALLOW"), but nothing
                # ever revoked it after a match — it silently behaved
                # identically to ALLOW_SESSION for its whole TTL window.
                # Consuming it here, at the moment it satisfies a check,
                # is what actually makes "once" mean once; whoever calls
                # this (tool_execution.py) commits the session afterward
                # regardless of whether the tool call itself goes on to
                # succeed — the authorization was for one *attempt*, not
                # contingent on that attempt's own outcome.
                grant.revoked_at = now
            return PolicyDecision(
                allowed=True,
                requires_confirmation=False,
                reason="Matched a valid, unexpired PermissionGrant.",
                matched_grant_id=grant.id,
            )

        return PolicyDecision(
            allowed=False,
            requires_confirmation=True,
            reason="No valid PermissionGrant found for this tool/target; "
            "user confirmation required.",
        )


policy_engine = PolicyEngine()
