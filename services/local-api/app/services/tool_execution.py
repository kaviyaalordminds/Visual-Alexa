"""Tool execution orchestrator — wires Policy Engine -> Tool Registry ->
Executor -> Audit Log -> Event Bus into the single path every tool call
takes. docs/security/01-SECURITY-ARCHITECTURE.md §1 (the core chain).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import (
    ErrorCategory,
    ErrorInfo,
    EventType,
    ToolCallRequest,
    ToolResult,
    ToolResultStatus,
)

from app.core.event_bus import event_bus
from app.services.audit import write_audit_log
from app.services.policy_engine import PolicyDecision, policy_engine
from app.services.tool_registry import ToolRegistry


class UnknownToolError(LookupError):
    pass


@dataclass
class ExecutionOutcome:
    result: ToolResult
    policy_decision: PolicyDecision


async def execute_tool_call(
    session: AsyncSession,
    registry: ToolRegistry,
    *,
    call: ToolCallRequest,
    user_id: str,
) -> ExecutionOutcome:
    definition = registry.get(call.tool_id)
    if definition is None:
        raise UnknownToolError(f"Tool '{call.tool_id}' is not registered.")

    if not registry.is_enabled(call.tool_id):
        # docs/phase-7/TOOL-REGISTRY.md — a disabled tool never even
        # reaches the Policy Engine; this is a stronger, earlier gate
        # than a denied permission (the tool isn't available at all
        # right now, regardless of who's asking).
        result = ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.FAILURE,
            error=ErrorInfo.build(
                code=ErrorCategory.TOOL_DISABLED,
                message=f"Tool '{call.tool_id}' is currently disabled.",
                correlation_id=call.correlation_id,
            ),
            duration_ms=0,
        )
        await write_audit_log(
            session,
            correlation_id=call.correlation_id,
            user_id=user_id,
            tool_id=call.tool_id,
            action=call.tool_id,
            target=call.target,
            risk_level=definition.risk_level,
            permission_grant_id=None,
            request_payload_summary=call.arguments,
            result_status=ToolResultStatus.FAILURE,
            error_code=ErrorCategory.TOOL_DISABLED.value,
            evidence_tier_used=None,
            duration_ms=0,
        )
        await event_bus.publish_type(
            EventType.ASSISTANT_ERROR, call.correlation_id, {"reason": "tool disabled"}
        )
        return ExecutionOutcome(
            result=result,
            policy_decision=PolicyDecision(
                allowed=False, requires_confirmation=False, reason="Tool disabled."
            ),
        )

    decision = await policy_engine.evaluate(
        session,
        user_id=user_id,
        tool_id=call.tool_id,
        risk_level=definition.risk_level,
        target=call.target,
    )

    if not decision.allowed:
        result = ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.FAILURE,
            error=ErrorInfo.build(
                code=ErrorCategory.PERMISSION_DENIED,
                message=decision.reason,
                correlation_id=call.correlation_id,
                user_action_required=decision.requires_confirmation,
            ),
            duration_ms=0,
        )
        await write_audit_log(
            session,
            correlation_id=call.correlation_id,
            user_id=user_id,
            tool_id=call.tool_id,
            action=call.tool_id,
            target=call.target,
            risk_level=definition.risk_level,
            permission_grant_id=None,
            request_payload_summary=call.arguments,
            result_status=ToolResultStatus.FAILURE,
            error_code=ErrorCategory.PERMISSION_DENIED.value,
            evidence_tier_used=None,
            duration_ms=0,
        )
        await event_bus.publish_type(
            EventType.ASSISTANT_ERROR, call.correlation_id, {"reason": decision.reason}
        )
        return ExecutionOutcome(result=result, policy_decision=decision)

    executor = registry.get_executor(call.tool_id)
    if executor is None:
        raise UnknownToolError(f"Tool '{call.tool_id}' has no registered executor.")

    await event_bus.publish_type(EventType.ASSISTANT_EXECUTING, call.correlation_id)
    result = await executor.execute(call)

    await write_audit_log(
        session,
        correlation_id=call.correlation_id,
        user_id=user_id,
        tool_id=call.tool_id,
        action=call.tool_id,
        target=call.target,
        risk_level=definition.risk_level,
        permission_grant_id=decision.matched_grant_id,
        request_payload_summary=call.arguments,
        result_status=result.status,
        error_code=result.error.code.value if result.error else None,
        evidence_tier_used=result.evidence_tier_used,
        duration_ms=result.duration_ms,
    )

    event_type = (
        EventType.TASK_COMPLETED
        if result.status == ToolResultStatus.SUCCESS
        else EventType.ASSISTANT_ERROR
    )
    await event_bus.publish_type(event_type, call.correlation_id, {"tool_id": call.tool_id})

    return ExecutionOutcome(result=result, policy_decision=decision)
