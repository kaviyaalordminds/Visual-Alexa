"""Shared plumbing for every computer-control tool executor. Every
executor in this subpackage is built with `callable_executor`, so the
result-mapping, error-mapping, and PLATFORM_NOT_SUPPORTED behavior is
defined exactly once rather than copy-pasted 30+ times.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from computer_control.core.results import ActionResult, ActionStatus
from pydantic import ValidationError
from veyra_contracts import (
    ErrorCategory,
    ErrorInfo,
    EvidenceTier,
    ToolCallRequest,
    ToolResult,
    ToolResultStatus,
)

from app.services.computer_control.gating import computer_control_enabled

T = TypeVar("T")

ToolFn = Callable[[ToolCallRequest], Awaitable[ActionResult]]

_STATUS_MAP: dict[ActionStatus, ToolResultStatus] = {
    ActionStatus.EXECUTED: ToolResultStatus.SUCCESS,
    ActionStatus.VERIFIED: ToolResultStatus.SUCCESS,
    ActionStatus.FAILED: ToolResultStatus.FAILURE,
    ActionStatus.PARTIAL: ToolResultStatus.FAILURE,
    ActionStatus.DENIED: ToolResultStatus.FAILURE,
    ActionStatus.UNKNOWN: ToolResultStatus.FAILURE,
    ActionStatus.TIMEOUT: ToolResultStatus.TIMEOUT,
    ActionStatus.CANCELLED: ToolResultStatus.CANCELLED,
}


class ToolLogicError(Exception):
    """Raised by tool logic functions to short-circuit straight to a
    structured ErrorInfo, instead of every function hand-building
    ActionResult(status=FAILED, ...) on every error path."""

    def __init__(self, code: ErrorCategory, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _action_result_to_tool_result(
    call: ToolCallRequest, action_result: ActionResult, duration_ms: int
) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        status=_STATUS_MAP[action_result.status],
        output=action_result.model_dump(mode="json"),
        error=action_result.error,
        evidence_tier_used=action_result.evidence_tier,
        duration_ms=duration_ms,
    )


def callable_executor(
    tool_id: str,
    fn: Callable[[ToolCallRequest], Awaitable[ActionResult]],
    default_evidence_tier: EvidenceTier | None = None,
):
    """Wraps a `(call) -> ActionResult` coroutine as a
    veyra_contracts ToolExecutor. Catches ToolLogicError and pydantic
    ValidationError (the latter mapped to TARGET_CONTEXT_REQUIRED when it
    comes from constructing an InputTarget/UISelector with no criteria —
    see docs/phase-2 §16) so individual tool functions never need
    repetitive try/except boilerplate for the common failure shapes.

    `default_evidence_tier`, when given, fills in
    `ActionResult.evidence_tier` for a successful result that didn't set
    one itself — see docs/architecture/05-COMPUTER-CONTROL.md §1. Every
    tool in one capability domain (e.g. all filesystem.* tools) uses the
    same native-API/UI-Automation tier, so this is set once per domain in
    the corresponding *_tools.py module rather than at every individual
    ActionResult(...) construction."""

    class _Executor:
        async def execute(self, call: ToolCallRequest) -> ToolResult:
            start = time.monotonic()
            try:
                if not await computer_control_enabled():
                    raise ToolLogicError(
                        ErrorCategory.PERMISSION_DENIED,
                        "Computer control is not enabled — see the "
                        "'computer_control.enabled' system setting "
                        "(docs/security/05-DATA-PROTECTION.md §3).",
                    )
                result = await fn(call)
            except ToolLogicError as exc:
                result = ActionResult(
                    status=ActionStatus.FAILED,
                    tool=tool_id,
                    target=call.target,
                    execution_time_ms=0,
                    error=ErrorInfo.build(exc.code, exc.message, call.correlation_id),
                )
            except ValidationError as exc:
                result = ActionResult(
                    status=ActionStatus.FAILED,
                    tool=tool_id,
                    target=call.target,
                    execution_time_ms=0,
                    error=ErrorInfo.build(
                        ErrorCategory.TARGET_CONTEXT_REQUIRED,
                        f"Missing or invalid target for '{tool_id}': {exc}",
                        call.correlation_id,
                        user_action_required=True,
                    ),
                )
            duration_ms = int((time.monotonic() - start) * 1000)
            updates: dict[str, object] = {"execution_time_ms": duration_ms}
            if result.evidence_tier is None and default_evidence_tier is not None:
                updates["evidence_tier"] = default_evidence_tier
            result = result.model_copy(update=updates)
            return _action_result_to_tool_result(call, result, duration_ms)

    return _Executor()


def platform_unsupported_executor(tool_id: str):
    """Used when this process's platform doesn't support the capability a
    tool needs (i.e. anywhere other than Windows) — fails safely and
    honestly rather than crashing, no-op'ing, or pretending to succeed.
    docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2."""

    async def _unsupported(call: ToolCallRequest) -> ActionResult:
        raise ToolLogicError(
            ErrorCategory.PLATFORM_NOT_SUPPORTED,
            f"'{tool_id}' requires Windows and is not available on this host.",
        )

    return callable_executor(tool_id, _unsupported)
