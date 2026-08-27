"""docs/security/02-PERMISSION-MODEL.md §3 — the Policy Engine's decision
rule is the single enforcement point for every tool call. These tests
exercise it directly against a real database session.
"""

from datetime import UTC, datetime, timedelta

import pytest
from app.api.deps import get_or_create_local_user
from app.models.tool import PermissionGrant as PermissionGrantRow
from app.services.policy_engine import policy_engine
from veyra_contracts import PermissionDecision, RiskLevel


async def _grant(session, user_id, **overrides):
    defaults = {
        "user_id": user_id,
        "tool_id": "filesystem.move",
        "target": None,
        "risk_level": RiskLevel.MODERATE,
        "scope": PermissionDecision.ALWAYS_ALLOW,
        "granted_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    row = PermissionGrantRow(**defaults)
    session.add(row)
    await session.commit()
    return row


@pytest.mark.asyncio
async def test_safe_tools_allowed_without_any_grant(db_session):
    decision = await policy_engine.evaluate(
        db_session,
        user_id="u1",
        tool_id="system.get_status",
        risk_level=RiskLevel.SAFE,
        target=None,
    )
    assert decision.allowed is True
    assert decision.requires_confirmation is False


@pytest.mark.asyncio
async def test_moderate_denied_without_grant(db_session):
    decision = await policy_engine.evaluate(
        db_session,
        user_id="u1",
        tool_id="filesystem.move",
        risk_level=RiskLevel.MODERATE,
        target=None,
    )
    assert decision.allowed is False
    assert decision.requires_confirmation is True


@pytest.mark.asyncio
async def test_moderate_allowed_with_valid_grant(db_session):
    user = await get_or_create_local_user(db_session)
    await _grant(db_session, user.id)
    decision = await policy_engine.evaluate(
        db_session,
        user_id=user.id,
        tool_id="filesystem.move",
        risk_level=RiskLevel.MODERATE,
        target=None,
    )
    assert decision.allowed is True
    assert decision.matched_grant_id is not None


@pytest.mark.asyncio
async def test_expired_grant_does_not_satisfy_check(db_session):
    user = await get_or_create_local_user(db_session)
    await _grant(db_session, user.id, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    decision = await policy_engine.evaluate(
        db_session,
        user_id=user.id,
        tool_id="filesystem.move",
        risk_level=RiskLevel.MODERATE,
        target=None,
    )
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_revoked_grant_does_not_satisfy_check(db_session):
    user = await get_or_create_local_user(db_session)
    await _grant(db_session, user.id, revoked_at=datetime.now(UTC))
    decision = await policy_engine.evaluate(
        db_session,
        user_id=user.id,
        tool_id="filesystem.move",
        risk_level=RiskLevel.MODERATE,
        target=None,
    )
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_grant_scoped_to_a_target_does_not_match_a_different_target(db_session):
    user = await get_or_create_local_user(db_session)
    await _grant(db_session, user.id, target="C:\\Users\\me\\report.docx")
    decision = await policy_engine.evaluate(
        db_session,
        user_id=user.id,
        tool_id="filesystem.move",
        risk_level=RiskLevel.MODERATE,
        target="C:\\Users\\me\\other-file.docx",
    )
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_critical_never_satisfied_even_by_always_allow_grant(db_session):
    """docs/security/08-SENSITIVE-ACTION-POLICY.md §2 — the single most
    important security test in this suite: a CRITICAL action must always
    require fresh confirmation, no matter how permissive a stored grant is.
    """
    user = await get_or_create_local_user(db_session)
    await _grant(
        db_session,
        user.id,
        tool_id="filesystem.delete",
        risk_level=RiskLevel.CRITICAL,
        scope=PermissionDecision.ALWAYS_ALLOW,
    )
    decision = await policy_engine.evaluate(
        db_session,
        user_id=user.id,
        tool_id="filesystem.delete",
        risk_level=RiskLevel.CRITICAL,
        target=None,
    )
    assert decision.allowed is False
    assert decision.requires_confirmation is True
