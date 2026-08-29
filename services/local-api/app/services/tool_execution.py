"""Tool execution orchestrator — wires Policy Engine -> Tool Registry ->
Executor -> Audit Log -> Event Bus into the single path every tool call
takes. docs/security/01-SECURITY-ARCHITECTURE.md §1 (the core chain).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import (
    ErrorCategory,
    ErrorInfo,
    EventType,
    ToolCallRequest,
    ToolCategory,
    ToolResult,
    ToolResultStatus,
)

from app.core.event_bus import event_bus
from app.core.logging import reset_correlation_id, set_correlation_id
from app.services.audit import write_audit_log
from app.services.policy_engine import PolicyDecision, policy_engine
from app.services.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class UnknownToolError(LookupError):
    pass


@dataclass
class ExecutionOutcome:
    result: ToolResult
    policy_decision: PolicyDecision


# Phase 13 (docs/phase-13-audit.md §4) — a real idempotency mechanism.
# `ToolCallRequest.call_id` already defaults to a fresh UUID per call, so
# by construction this cache only ever hits when a *caller* deliberately
# reuses a call_id across attempts — the common case (a fresh call_id
# every time) is unaffected. `AgentOrchestrator` is the one caller that
# does this deliberately, for a step being retried by `RecoveryManager`
# (see orchestrator.py's `_step_call_id`) — so that a retry after a
# transient failure (e.g. the underlying action actually succeeded but
# the response was lost) replays the cached result instead of executing
# the action a second time. Bounded like every other in-memory registry
# in this codebase (LoopBudgetTracker, the cancellation/pause event
# dicts): a TTL plus a max size with oldest-first eviction, never
# unbounded growth.
_IDEMPOTENCY_CACHE_TTL_SECONDS = 300
_IDEMPOTENCY_CACHE_MAX_SIZE = 500


@dataclass
class _CachedOutcome:
    outcome: ExecutionOutcome
    cached_at: float


_idempotency_cache: dict[str, _CachedOutcome] = {}


def _idempotency_cache_get(call_id: str) -> ExecutionOutcome | None:
    entry = _idempotency_cache.get(call_id)
    if entry is None:
        return None
    if time.monotonic() - entry.cached_at > _IDEMPOTENCY_CACHE_TTL_SECONDS:
        _idempotency_cache.pop(call_id, None)
        return None
    return entry.outcome


def _idempotency_cache_put(call_id: str, outcome: ExecutionOutcome) -> None:
    if len(_idempotency_cache) >= _IDEMPOTENCY_CACHE_MAX_SIZE:
        oldest_key = min(_idempotency_cache, key=lambda k: _idempotency_cache[k].cached_at)
        _idempotency_cache.pop(oldest_key, None)
    _idempotency_cache[call_id] = _CachedOutcome(outcome=outcome, cached_at=time.monotonic())


def reset_idempotency_cache() -> None:
    """Test-isolation helper — process-global like every other registry
    here (device_pairing's permission cache, tool_registry), so one
    test's cached call_id must not leak into the next."""
    _idempotency_cache.clear()


async def execute_tool_call(
    session: AsyncSession,
    registry: ToolRegistry,
    *,
    call: ToolCallRequest,
    user_id: str,
) -> ExecutionOutcome:
    # Phase 13 (docs/phase-13-audit.md §5) — this is the single chokepoint
    # every tool call takes (orchestrator-driven or a direct
    # POST /tools/{id}/invoke alike), so it's the one real place to make
    # every log line emitted for the duration of this call carry the
    # call's own correlation_id — restored to whatever was in scope
    # before on the way out, never just cleared to None (correct for a
    # call nested inside a larger correlation_id'd scope, e.g. a future
    # caller that sets one of its own before invoking this).
    token = set_correlation_id(call.correlation_id)
    try:
        cached = _idempotency_cache_get(call.call_id)
        if cached is not None:
            logger.info(
                "[VEYRA] tool_execution: idempotent replay for call_id=%s (tool=%s) — "
                "returning the cached result instead of re-executing.",
                call.call_id,
                call.tool_id,
            )
            return cached
        outcome = await _execute_tool_call_uncached(session, registry, call=call, user_id=user_id)
        # Only a genuine SUCCESS is cached. A failure means (as far as
        # this process can tell) the real action never took effect, so a
        # retry with the same call_id must genuinely re-attempt it —
        # caching failures too would turn every transient error into a
        # permanent one, defeating RecoveryManager's own RETRY strategy.
        # Caching only successes is exactly the "don't double-send after
        # the response was lost but the action went through" case
        # Phase 13 §28 describes.
        if outcome.result.status == ToolResultStatus.SUCCESS:
            _idempotency_cache_put(call.call_id, outcome)
        return outcome
    finally:
        reset_correlation_id(token)


async def _execute_tool_call_uncached(
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
    # Phase 12 — IoT command observability, gated on category rather than
    # a second execution path: every IoT tool call (device.set_power,
    # device.set_temperature, ...) already flows through this exact
    # chokepoint, so this is the one place to publish from.
    is_iot = definition.category == ToolCategory.IOT
    if is_iot:
        await event_bus.publish_type(
            EventType.IOT_COMMAND_STARTED, call.correlation_id, {"tool_id": call.tool_id}
        )
    try:
        result = await executor.execute(call)
    except Exception:
        # CLAUDE.md: "Every tool call writes exactly one AuditLog row,
        # success or failure" — an unanticipated bug in a domain executor
        # must not be able to violate that. Write the row for this
        # otherwise-uncaught failure, publish the error event, then
        # re-raise so the underlying bug is still visible (never
        # swallowed) rather than reported as a clean tool failure.
        logger.exception(
            "[VEYRA] Unhandled exception from executor for tool '%s'", call.tool_id
        )
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
            result_status=ToolResultStatus.FAILURE,
            error_code=ErrorCategory.UNKNOWN_ERROR.value,
            evidence_tier_used=None,
            duration_ms=0,
        )
        await event_bus.publish_type(
            EventType.ASSISTANT_ERROR,
            call.correlation_id,
            {"reason": "unhandled executor exception", "tool_id": call.tool_id},
        )
        raise

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
    if is_iot:
        await event_bus.publish_type(
            EventType.IOT_COMMAND_COMPLETED,
            call.correlation_id,
            {"tool_id": call.tool_id, "status": result.status.value},
        )

    return ExecutionOutcome(result=result, policy_decision=decision)
