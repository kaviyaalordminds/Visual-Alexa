"""docs/security/06-AUDIT-LOGGING.md — every tool call writes exactly one
AuditLog row, success or failure.
"""

import pytest
from app.models.audit import AuditLog
from sqlalchemy import select


async def test_successful_invocation_writes_an_audit_row(client, db_session):
    resp = await client.post("/tools/system.get_status/invoke", json={})
    assert resp.status_code == 200
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.tool_id == "system.get_status")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].result_status.value == "SUCCESS"
    assert rows[0].risk_level.value == "SAFE"


async def test_denied_invocation_still_writes_an_audit_row(client, db_session):
    # filesystem.move is not registered as a tool in Phase 1, so exercise
    # the denial path directly through the orchestrator instead of the API
    # (the API 404s before reaching the policy engine for unknown tools —
    # see test_invoke_unknown_tool_is_404). Registering a synthetic
    # MODERATE tool proves the deny-and-audit path for a tool that *is*
    # known but lacks a permission grant.
    from app.services.tool_execution import execute_tool_call
    from app.services.tool_registry import tool_registry
    from veyra_contracts import RiskLevel, ToolCallRequest, ToolCategory, ToolDefinition

    class _NoopExecutor:
        async def execute(self, call):  # pragma: no cover - never reached, denied first
            raise AssertionError("executor must not run when policy denies the call")

    definition = ToolDefinition(
        id="test.moderate_tool",
        name="Test Moderate Tool",
        description="synthetic",
        category=ToolCategory.SYSTEM,
        input_schema={},
        output_schema={},
        risk_level=RiskLevel.MODERATE,
        required_permission="test.moderate",
    )
    tool_registry.register(definition, _NoopExecutor())

    call = ToolCallRequest(tool_id="test.moderate_tool", correlation_id="corr-denied")
    outcome = await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")

    assert outcome.result.status == "FAILURE"
    assert outcome.policy_decision.allowed is False

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.tool_id == "test.moderate_tool")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].result_status.value == "FAILURE"
    assert rows[0].error_code == "PERMISSION_DENIED"


async def test_executor_crash_still_writes_an_audit_row(db_session):
    """Phase 9 audit P1-3: an unanticipated bug in a domain executor must
    not be able to violate "every tool call writes exactly one AuditLog
    row, success or failure" — the audit row must exist even when the
    executor raises something no one anticipated, and the original
    exception must still propagate (never silently swallowed as a clean
    failure)."""
    from app.services.tool_execution import execute_tool_call
    from app.services.tool_registry import tool_registry
    from veyra_contracts import RiskLevel, ToolCallRequest, ToolCategory, ToolDefinition

    class _CrashingExecutor:
        async def execute(self, call):
            raise RuntimeError("simulated unanticipated executor bug")

    definition = ToolDefinition(
        id="test.crashing_tool",
        name="Test Crashing Tool",
        description="synthetic",
        category=ToolCategory.SYSTEM,
        input_schema={},
        output_schema={},
        risk_level=RiskLevel.SAFE,
        required_permission="test.crashing",
    )
    tool_registry.register(definition, _CrashingExecutor())

    call = ToolCallRequest(tool_id="test.crashing_tool", correlation_id="corr-crash")
    with pytest.raises(RuntimeError, match="simulated unanticipated executor bug"):
        await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.tool_id == "test.crashing_tool")
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].result_status.value == "FAILURE"
    assert rows[0].error_code == "UNKNOWN_ERROR"
