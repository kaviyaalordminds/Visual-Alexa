"""Phase 13 (docs/phase-13-audit.md §4) — real idempotency: a caller that
deliberately reuses a `ToolCallRequest.call_id` (as `AgentOrchestrator`
does for a retried step, see orchestrator.py's `_step_call_id`) must get
the cached result of a prior *successful* call rather than a second real
execution. A failed call must never be cached — a retry after a genuine
failure must still genuinely retry.
"""

from __future__ import annotations

from app.core.logging import get_correlation_id
from app.services.tool_execution import execute_tool_call
from app.services.tool_registry import tool_registry
from veyra_contracts import (
    ErrorCategory,
    ErrorInfo,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)


class _CountingExecutor:
    """Fails on its first `fail_first_n` invocations, then succeeds —
    counts real invocations so a test can prove the cache prevented one."""

    def __init__(self, *, fail_first_n: int = 0) -> None:
        self.call_count = 0
        self._fail_first_n = fail_first_n

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        self.call_count += 1
        if self.call_count <= self._fail_first_n:
            return ToolResult(
                call_id=call.call_id,
                status=ToolResultStatus.FAILURE,
                error=ErrorInfo.build(
                    code=ErrorCategory.TIMEOUT,
                    message="simulated transient failure",
                    correlation_id=call.correlation_id,
                ),
                duration_ms=1,
            )
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output={"invocation": self.call_count},
            duration_ms=1,
        )


def _register(tool_id: str, executor: object) -> None:
    tool_registry.register(
        ToolDefinition(
            id=tool_id,
            name=tool_id,
            description="test",
            category=ToolCategory.SYSTEM,
            input_schema={},
            output_schema={},
            risk_level=RiskLevel.SAFE,
            required_permission=tool_id,
        ),
        executor,
    )


async def test_replaying_a_successful_call_id_never_re_executes(db_session):
    executor = _CountingExecutor()
    _register("test.idempotent_success", executor)

    call = ToolCallRequest(
        tool_id="test.idempotent_success", correlation_id="corr-1", call_id="stable-call-id-1"
    )
    first = await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")
    assert first.result.status == ToolResultStatus.SUCCESS
    assert executor.call_count == 1

    replay = await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")
    assert replay.result.status == ToolResultStatus.SUCCESS
    assert replay.result.output == first.result.output
    # The executor was never invoked a second time — this is the whole
    # point: a duplicate call with the same call_id must not double-act.
    assert executor.call_count == 1


async def test_replaying_a_failed_call_id_genuinely_retries(db_session):
    """A failure means (as far as this process can tell) nothing real
    happened — caching it would turn every transient error into a
    permanent one and break RecoveryManager's own RETRY strategy."""
    executor = _CountingExecutor(fail_first_n=1)
    _register("test.idempotent_retry_after_failure", executor)

    call = ToolCallRequest(
        tool_id="test.idempotent_retry_after_failure",
        correlation_id="corr-2",
        call_id="stable-call-id-2",
    )
    first = await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")
    assert first.result.status == ToolResultStatus.FAILURE
    assert executor.call_count == 1

    retry = await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")
    assert retry.result.status == ToolResultStatus.SUCCESS
    # A genuine second execution happened — the failure was never cached.
    assert executor.call_count == 2


async def test_execute_tool_call_sets_correlation_id_for_the_call_and_restores_it_after(
    db_session,
):
    """docs/phase-13-audit.md §5 — the one chokepoint every tool call
    takes now sets the log correlation_id for real, and restores the
    prior scope afterward rather than leaking it into unrelated code
    that runs later in the same async context."""
    observed: dict[str, str | None] = {}

    class _ObservingExecutor:
        async def execute(self, call: ToolCallRequest) -> ToolResult:
            observed["during"] = get_correlation_id()
            return ToolResult(call_id=call.call_id, status=ToolResultStatus.SUCCESS, duration_ms=1)

    _register("test.idempotent_correlation_id", _ObservingExecutor())

    assert get_correlation_id() is None
    call = ToolCallRequest(tool_id="test.idempotent_correlation_id", correlation_id="corr-xyz")
    await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")

    assert observed["during"] == "corr-xyz"
    assert get_correlation_id() is None


async def test_two_different_call_ids_are_never_conflated(db_session):
    executor = _CountingExecutor()
    _register("test.idempotent_distinct_calls", executor)

    call_a = ToolCallRequest(
        tool_id="test.idempotent_distinct_calls", correlation_id="corr-3", call_id="call-a"
    )
    call_b = ToolCallRequest(
        tool_id="test.idempotent_distinct_calls", correlation_id="corr-3", call_id="call-b"
    )
    await execute_tool_call(db_session, tool_registry, call=call_a, user_id="u1")
    await execute_tool_call(db_session, tool_registry, call=call_b, user_id="u1")
    # Two genuinely distinct calls (default behavior — a fresh call_id
    # per invocation is what every non-retry caller in this codebase
    # already does) both really executed.
    assert executor.call_count == 2
