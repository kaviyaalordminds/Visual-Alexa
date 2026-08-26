"""AgentOrchestrator — the central coordinator (docs/phase-4/AGENT-ARCHITECTURE.md).
No multi-agent fan-out (brief §5): one orchestrator, calling specialized,
already-existing capabilities (Phase 2/3 tools) through the one Tool
Registry/Policy Engine path every other caller uses
(docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §6).

Responsibilities: receive a task, understand it, plan it, validate/
authorize/execute it in a closed OBSERVE->ACT->OBSERVE->VERIFY loop,
recover from failure within budget, ask for clarification/confirmation,
and terminate safely — cancellable and timed-out, never an unbounded
loop.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import (
    ErrorCategory,
    EventType,
    ExecutionPlan,
    PlanStep,
    RecoveryStrategy,
    TaskBudget,
    TaskState,
    ToolCallRequest,
    ToolResultStatus,
)

from app.core.event_bus import event_bus
from app.models.task import Task as TaskRow
from app.models.task import TaskStep as TaskStepRow
from app.services.agent.confirmation import ConfirmationManager
from app.services.agent.context import ContextManager, StepRecord, TaskContext
from app.services.agent.intent import IntentInterpreter
from app.services.agent.loop_protection import LoopBudgetTracker
from app.services.agent.planner import FileCandidate, TaskPlanner
from app.services.agent.recovery import RecoveryManager
from app.services.agent.state_machine import TaskStateMachine
from app.services.agent.tool_selector import ToolSelector
from app.services.tool_execution import execute_tool_call
from app.services.tool_registry import ToolRegistry

# One process-wide cancellation registry keyed by task id. This process is
# the only one that ever runs a task (CLAUDE.md: Local API is the only
# process that can invoke a tool), so an in-memory dict is sufficient —
# no second persistence mechanism for a purely runtime signal.
_cancellation_events: dict[str, asyncio.Event] = {}


def request_cancellation(task_id: str) -> None:
    _cancellation_events.setdefault(task_id, asyncio.Event()).set()


def _is_cancelled(task_id: str) -> bool:
    event = _cancellation_events.get(task_id)
    return event is not None and event.is_set()


def _clear_cancellation(task_id: str) -> None:
    _cancellation_events.pop(task_id, None)


def _now() -> datetime:
    return datetime.now(UTC)


class AgentOrchestrator:
    def __init__(self, registry: ToolRegistry, search_roots: list[str]) -> None:
        self._registry = registry
        self._tool_selector = ToolSelector(registry)
        self._planner = TaskPlanner(self._tool_selector, search_roots)
        self._intent = IntentInterpreter()
        self._confirmation = ConfirmationManager()
        self._recovery = RecoveryManager()
        self._context_manager = ContextManager()

    async def run(self, session: AsyncSession, task: TaskRow) -> None:
        sm = TaskStateMachine(task)
        budget = TaskBudget(
            max_steps=task.max_steps,
            timeout_seconds=task.timeout_seconds,
            max_recovery_attempts=task.max_recovery_attempts,
            max_replans=task.max_replans,
        )
        tracker = LoopBudgetTracker(budget=budget)
        context = TaskContext(task_id=task.id, user_goal=task.description)

        task.started_at = _now()
        sm.transition(TaskState.UNDERSTANDING)
        await self._save(session, task)
        await event_bus.publish_type(
            EventType.TASK_CREATED, task.correlation_id, {"task_id": task.id}
        )

        intent = self._intent.interpret(task.description)
        task.normalized_goal = intent.model_dump(mode="json")
        context.entities = intent.entities

        if await self._check_cancelled(session, sm, task):
            return

        if intent.status in ("AMBIGUOUS", "MISSING_INFORMATION"):
            await self._wait_for_user(
                session, sm, task, intent.clarifying_question, "clarification"
            )
            return

        # UNSAFE and any other non-UNDERSTOOD status still passes through
        # PLANNING -> WAITING_PERMISSION -> FAILED: docs/phase-4 §37 — a
        # request matching a disallowed pattern is never planned, but the
        # only legal exit from PLANNING is the same authorization gate
        # every real plan goes through, so the *reason* it never executes
        # is what differs (failure_reason), not the state path.
        sm.transition(TaskState.PLANNING)
        await self._save(session, task)
        await event_bus.publish_type(EventType.TASK_PLANNED, task.correlation_id)

        if intent.status != "UNDERSTOOD":
            await self._fail_at_planning(
                session, sm, task, ErrorCategory.PERMISSION_DENIED, "Request was classified UNSAFE."
            )
            return

        outcome = await self._planner.create_plan(
            intent, search=self._make_search_fn(session, task)
        )

        if outcome.status == "AMBIGUOUS":
            sm.transition(TaskState.WAITING_USER)
            task.result = {"clarifying_question": outcome.clarifying_question}
            await self._save(session, task)
            await event_bus.publish_type(EventType.TASK_CONFIRMATION_REQUIRED, task.correlation_id)
            return

        if outcome.status in ("CAPABILITY_UNAVAILABLE", "UNSAFE", "INVALID"):
            code = {
                "CAPABILITY_UNAVAILABLE": ErrorCategory.CAPABILITY_UNAVAILABLE,
                "UNSAFE": ErrorCategory.PERMISSION_DENIED,
                "INVALID": ErrorCategory.INVALID_PLAN,
            }[outcome.status]
            await self._fail_at_planning(session, sm, task, code, outcome.reason or outcome.status)
            return

        plan = outcome.plan
        assert plan is not None
        task.total_steps = len(plan.steps)
        task.risk_level = plan.risk_level
        task.requires_confirmation = plan.requires_confirmation
        sm.transition(TaskState.WAITING_PERMISSION)
        await self._save(session, task)
        sm.transition(TaskState.EXECUTING)
        await self._save(session, task)

        await self._execute_plan(session, sm, task, plan, tracker, context)

    async def resume_after_confirmation(self, session: AsyncSession, task: TaskRow) -> None:
        """docs/phase-4/CONFIRMATION.md — called after a matching
        `PermissionGrant` has been created for the pending step (via
        `POST /tasks/{id}/confirm`). Continues the *same* plan from the
        step that paused, never a full replan — the environment hasn't
        necessarily changed just because the user approved an action."""
        sm = TaskStateMachine(task)
        pending = task.result or {}
        plan_data = pending.get("pending_plan")
        if task.state != TaskState.WAITING_PERMISSION or not plan_data:
            raise ValueError("Task has no pending confirmation to resume.")

        plan = ExecutionPlan.model_validate(plan_data)
        budget = TaskBudget(
            max_steps=task.max_steps,
            timeout_seconds=task.timeout_seconds,
            max_recovery_attempts=task.max_recovery_attempts,
            max_replans=task.max_replans,
        )
        tracker = LoopBudgetTracker(budget=budget)
        context = TaskContext(task_id=task.id, user_goal=task.description)

        await event_bus.publish_type(EventType.TASK_CONFIRMATION_RECEIVED, task.correlation_id)
        sm.transition(TaskState.EXECUTING)
        task.result = {}
        await self._save(session, task)
        await self._execute_plan(session, sm, task, plan, tracker, context)

    async def _execute_plan(
        self,
        session: AsyncSession,
        sm: TaskStateMachine,
        task: TaskRow,
        plan: ExecutionPlan,
        tracker: LoopBudgetTracker,
        context: TaskContext,
    ) -> None:
        for step in plan.steps:
            if await self._check_cancelled(session, sm, task):
                return
            budget_reason = tracker.budget_exceeded_reason()
            if budget_reason:
                await self._timeout(session, sm, task, budget_reason)
                return
            if tracker.record_call_and_check_loop(step.tool_id, step.arguments):
                await self._timeout(session, sm, task, f"Loop detected repeating '{step.tool_id}'.")
                return

            tracker.record_step()
            task.current_step = step.sequence
            await self._save(session, task)

            step_row = TaskStepRow(
                task_id=task.id,
                step_number=step.sequence,
                state=TaskState.EXECUTING,
                tool_id=step.tool_id,
                description=step.description,
                intent={"goal": plan.goal, "step_intent": step.intent},
                arguments=step.arguments,
                expected_outcome=step.expected_outcome,
                risk_level=step.risk_level,
                confidence=step.confidence,
                started_at=_now(),
            )
            session.add(step_row)
            await session.flush()
            await event_bus.publish_type(
                EventType.TASK_STEP_STARTED, task.correlation_id, {"step": step.sequence}
            )

            result = await self._call_tool(session, task, step.tool_id, step.arguments)
            step_row.actual_result = result.model_dump(mode="json") if result else None
            step_row.completed_at = _now()

            if result is None:
                # UNKNOWN_TOOL — brief §77: reject, never execute.
                step_row.state = TaskState.FAILED
                step_row.error = {"code": ErrorCategory.UNKNOWN_TOOL.value}
                await self._save(session, task)
                await self._fail(session, sm, task, "Planned tool is not registered.")
                return

            if (
                result.status == ToolResultStatus.FAILURE
                and result.error is not None
                and result.error.code == ErrorCategory.PERMISSION_DENIED
                and result.error.user_action_required
            ):
                step_row.state = TaskState.WAITING_PERMISSION
                await self._save(session, task)
                definition = self._tool_selector.select(step.tool_id)
                prompt = self._confirmation.build_prompt(step, definition)
                sm.transition(TaskState.WAITING_PERMISSION)
                target = step.arguments.get("path") or step.arguments.get("application")
                task.result = {
                    "confirmation_prompt": prompt,
                    "pending_tool_id": step.tool_id,
                    "pending_target": target,
                    "pending_risk_level": step.risk_level.value,
                    # docs/phase-4/CONFIRMATION.md — the *remaining* plan
                    # (this step onward), so resuming continues exactly
                    # where execution paused rather than replanning.
                    "pending_plan": plan.model_copy(
                        update={"steps": [s for s in plan.steps if s.sequence >= step.sequence]}
                    ).model_dump(mode="json"),
                }
                await self._save(session, task)
                await event_bus.publish_type(
                    EventType.TASK_CONFIRMATION_REQUIRED, task.correlation_id, {"prompt": prompt}
                )
                return

            if result.status != ToolResultStatus.SUCCESS:
                step_row.state = TaskState.FAILED
                error_code = result.error.code if result.error else ErrorCategory.UNKNOWN_ERROR
                step_row.error = {
                    "code": error_code.value,
                    "message": result.error.message if result.error else None,
                }
                context.record_error(f"step {step.sequence} ({step.tool_id}): {error_code.value}")
                await self._save(session, task)
                await event_bus.publish_type(
                    EventType.TASK_STEP_FAILED, task.correlation_id, {"step": step.sequence}
                )
                recovered = await self._recover(
                    session, sm, task, plan, step, error_code, tracker, context
                )
                if not recovered:
                    return
                continue

            step_row.state = TaskState.COMPLETED
            context.record_step(
                StepRecord(
                    sequence=step.sequence,
                    tool_id=step.tool_id,
                    status="SUCCESS",
                    summary=step.description,
                )
            )
            await self._save(session, task)
            await event_bus.publish_type(
                EventType.TASK_STEP_COMPLETED, task.correlation_id, {"step": step.sequence}
            )

        task.completed_at = _now()
        task.result = {"outcome": "success"}
        sm.transition(TaskState.OBSERVING)
        await self._save(session, task)
        sm.transition(TaskState.VERIFYING)
        await self._save(session, task)
        sm.transition(TaskState.COMPLETED)
        await self._save(session, task)
        _clear_cancellation(task.id)

    async def _recover(
        self,
        session: AsyncSession,
        sm: TaskStateMachine,
        task: TaskRow,
        plan: ExecutionPlan,
        step: PlanStep,
        error_code: ErrorCategory,
        tracker: LoopBudgetTracker,
        context: TaskContext,
    ) -> bool:
        """Returns True if the caller should continue the step loop
        (i.e. a retry was already performed and succeeded), False if the
        task reached a terminal/waiting state and the caller must stop."""
        sm.transition(TaskState.RECOVERING)
        await self._save(session, task)
        await event_bus.publish_type(EventType.TASK_RECOVERY_STARTED, task.correlation_id)

        decision = self._recovery.decide(
            error_code=error_code,
            retry_count=context.retry_count,
            replan_count=context.replan_count,
            budget=TaskBudget(
                max_steps=task.max_steps,
                timeout_seconds=task.timeout_seconds,
                max_recovery_attempts=task.max_recovery_attempts,
                max_replans=task.max_replans,
            ),
        )
        context.retry_count = decision.retry_count

        retry_strategies = (
            RecoveryStrategy.RETRY,
            RecoveryStrategy.REGROUND,
            RecoveryStrategy.REOBSERVE,
        )
        if decision.strategy in retry_strategies:
            tracker.record_retry()
            sm.transition(TaskState.EXECUTING)
            await self._save(session, task)
            await event_bus.publish_type(EventType.TASK_RECOVERY_COMPLETED, task.correlation_id)
            result = await self._call_tool(session, task, step.tool_id, step.arguments)
            if result is not None and result.status == ToolResultStatus.SUCCESS:
                context.record_step(
                    StepRecord(
                        sequence=step.sequence,
                        tool_id=step.tool_id,
                        status="SUCCESS",
                        summary="recovered",
                    )
                )
                return True
            # Still failing — one more diagnosis pass, bounded by the
            # same budget (never an unbounded retry loop).
            next_code = result.error.code if (result and result.error) else error_code
            return await self._recover(session, sm, task, plan, step, next_code, tracker, context)

        if decision.strategy == RecoveryStrategy.REPLAN:
            context.replan_count += 1
            tracker.record_replan()
            budget_reason = tracker.budget_exceeded_reason()
            if budget_reason:
                await self._timeout(session, sm, task, budget_reason)
                return False
            sm.transition(TaskState.PLANNING)
            await self._save(session, task)
            await self._fail(session, sm, task, "Replanning is not yet supported for this goal.")
            return False

        if decision.strategy == RecoveryStrategy.ASK_USER:
            question = f"I ran into a problem: {decision.reason} How would you like to proceed?"
            await self._wait_for_user(session, sm, task, question, "recovery")
            return False

        await self._fail(session, sm, task, decision.reason)
        return False

    async def _call_tool(self, session: AsyncSession, task: TaskRow, tool_id: str, arguments: dict):
        if not self._tool_selector.exists(tool_id):
            return None
        call = ToolCallRequest(
            tool_id=tool_id,
            target=arguments.get("path") or arguments.get("application"),
            arguments=arguments,
            correlation_id=task.correlation_id,
        )
        outcome = await execute_tool_call(session, self._registry, call=call, user_id=task.user_id)
        return outcome.result

    def _make_search_fn(self, session: AsyncSession, task: TaskRow):
        async def _search(directory: str, filename_contains: str | None):
            args: dict = {"directory": directory}
            if filename_contains:
                args["filename_contains"] = filename_contains
            result = await self._call_tool(session, task, "filesystem.search", args)
            if result is None or result.status != ToolResultStatus.SUCCESS or not result.output:
                return []
            matches = (result.output.get("data") or {}).get("matches", [])
            candidates = []
            for m in matches:
                if m.get("is_directory"):
                    continue
                modified_at = m.get("modified_at")
                candidates.append(
                    FileCandidate(
                        path=m["path"],
                        name=m["name"],
                        modified_at=datetime.fromisoformat(modified_at) if modified_at else None,
                        size_bytes=m.get("size_bytes"),
                    )
                )
            return candidates

        return _search

    async def _wait_for_user(
        self,
        session,
        sm: TaskStateMachine,
        task: TaskRow,
        question: str | None,
        reason: str,
    ) -> None:
        sm.transition(TaskState.WAITING_USER)
        task.result = {
            **(task.result or {}),
            "clarifying_question": question,
            "waiting_reason": reason,
        }
        await self._save(session, task)
        await event_bus.publish_type(
            EventType.TASK_CONFIRMATION_REQUIRED, task.correlation_id, {"question": question}
        )

    async def _fail_at_planning(
        self,
        session,
        sm: TaskStateMachine,
        task: TaskRow,
        code: ErrorCategory,
        reason: str,
    ) -> None:
        sm.transition(TaskState.WAITING_PERMISSION)
        await self._save(session, task)
        await self._fail(session, sm, task, reason, code=code)

    async def _fail(
        self,
        session,
        sm: TaskStateMachine,
        task: TaskRow,
        reason: str,
        code: ErrorCategory | None = None,
    ) -> None:
        sm.transition(TaskState.FAILED)
        task.completed_at = _now()
        task.failure_reason = reason
        await self._save(session, task)
        await event_bus.publish_type(EventType.TASK_FAILED, task.correlation_id, {"reason": reason})
        _clear_cancellation(task.id)

    async def _timeout(self, session, sm: TaskStateMachine, task: TaskRow, reason: str) -> None:
        sm.transition(TaskState.TIMED_OUT)
        task.completed_at = _now()
        task.failure_reason = reason
        await self._save(session, task)
        await event_bus.publish_type(
            EventType.TASK_TIMED_OUT, task.correlation_id, {"reason": reason}
        )
        _clear_cancellation(task.id)

    async def _check_cancelled(self, session, sm: TaskStateMachine, task: TaskRow) -> bool:
        if not _is_cancelled(task.id):
            return False
        sm.transition(TaskState.CANCELLED)
        task.completed_at = _now()
        await self._save(session, task)
        await event_bus.publish_type(EventType.TASK_CANCELLED, task.correlation_id)
        _clear_cancellation(task.id)
        return True

    async def _save(self, session: AsyncSession, task: TaskRow) -> None:
        await session.commit()
        await session.refresh(task)
