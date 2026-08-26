"""docs/security/06-AUDIT-LOGGING.md — every tool call writes exactly one
AuditLog row, success or failure.
"""

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
