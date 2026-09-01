"""apply_confirmation_decision — the one place a `PermissionDecision` for a
paused `WAITING_PERMISSION` task turns into either a real `PermissionGrant`
(and the task becomes resumable) or a `CANCELLED` task.

Shared by the HTTP `/tasks/{id}/confirm` route and the voice layer's
confirmation handling (docs/phase-5/VOICE-SECURITY.md §46-49) so there is
exactly one confirmation code path, never two that could silently diverge
— CLAUDE.md: "Never duplicate services." Extracted from what was
previously `app/api/tasks.py`'s `confirm_task` handler inline logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import EventType, PermissionDecision, TaskState

from app.api.deps import get_or_create_local_user
from app.core.event_bus import event_bus
from app.models.task import Task as TaskRow
from app.models.tool import PermissionGrant as PermissionGrantRow
from app.services.agent.state_machine import TaskStateMachine

# docs/security/08-SENSITIVE-ACTION-POLICY.md §1: MODERATE defaults to
# ALLOW_SESSION after first approval, SENSITIVE "may be relaxed to
# ALWAYS_ALLOW per-tool by explicit user choice" — three genuinely
# different lifetimes, not the same flat grant with three different
# labels. ALLOW_ONCE is true single-use (tool_execution.py revokes it
# right after the one call it covers, so its expiry here is just a safety
# net for a call that never happens). ALLOW_SESSION covers a normal
# working session without demanding CLAUDE.md's "no standing ALWAYS_ALLOW
# for anything the user didn't explicitly choose" be stretched to mean
# "session == forever." ALWAYS_ALLOW has no expiry — revocable any time
# via /permissions, never silently reinstated.
_ALLOW_ONCE_TTL_SECONDS = 300
_ALLOW_SESSION_TTL_SECONDS = 4 * 60 * 60


class NoPendingConfirmationError(ValueError):
    """Raised when `task` has no pending WAITING_PERMISSION confirmation
    to apply a decision to."""


async def apply_confirmation_decision(
    session: AsyncSession, task: TaskRow, decision: PermissionDecision
) -> bool:
    """Returns True if the task is now ready to resume execution (the
    caller is responsible for actually running
    `AgentOrchestrator.resume_after_confirmation` — in whatever execution
    context, background task or inline await, fits that caller), False if
    the task was denied/cancelled outright and there is nothing further to
    do."""
    if task.state != TaskState.WAITING_PERMISSION or not (task.result or {}).get("pending_plan"):
        raise NoPendingConfirmationError("Task has no pending confirmation to resume.")

    pending_tool_id = (task.result or {}).get("pending_tool_id")
    pending_target = (task.result or {}).get("pending_target")

    if decision in (PermissionDecision.DENY, PermissionDecision.CANCEL):
        # docs/phase-4 §21 — "Do not interpret ambiguous responses as
        # confirmation." A paused task has no running orchestrator loop
        # left to observe a cooperative-cancellation signal, so denial
        # transitions the task directly rather than relying on one.
        sm = TaskStateMachine(task)
        sm.transition(TaskState.CANCELLED)
        task.completed_at = datetime.now(UTC)
        task.result = {"outcome": "denied_by_user"}
        await session.commit()
        await session.refresh(task)
        await event_bus.publish_type(
            EventType.PERMISSION_DENIED,
            task.correlation_id,
            {"tool_id": pending_tool_id, "target": pending_target},
        )
        return False

    user = await get_or_create_local_user(session)
    pending_risk = (task.result or {}).get("pending_risk_level")
    # Belt-and-suspenders alongside PolicyEngine's own risk_level ==
    # CRITICAL special case (docs/security/08-SENSITIVE-ACTION-POLICY.md
    # §2): a CRITICAL step reaching WAITING_PERMISSION and approved with
    # ALLOW_SESSION/ALWAYS_ALLOW must never leave a grant on disk that
    # *looks* like standing authorization for next time, even though
    # PolicyEngine.evaluate() already ignores any stored grant for
    # CRITICAL regardless. Every CRITICAL approval gets the shortest,
    # single-use lifetime no matter which decision was actually clicked.
    if pending_risk == "CRITICAL":
        expires_at = datetime.now(UTC) + timedelta(seconds=_ALLOW_ONCE_TTL_SECONDS)
    elif decision == PermissionDecision.ALWAYS_ALLOW:
        expires_at = None
    elif decision == PermissionDecision.ALLOW_SESSION:
        expires_at = datetime.now(UTC) + timedelta(seconds=_ALLOW_SESSION_TTL_SECONDS)
    else:
        expires_at = datetime.now(UTC) + timedelta(seconds=_ALLOW_ONCE_TTL_SECONDS)
    grant = PermissionGrantRow(
        user_id=user.id,
        tool_id=pending_tool_id,
        target=pending_target,
        risk_level=pending_risk,
        scope=decision,
        granted_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    session.add(grant)
    await session.commit()
    await session.refresh(task)
    await event_bus.publish_type(
        EventType.PERMISSION_APPROVED,
        task.correlation_id,
        {"tool_id": pending_tool_id, "target": pending_target, "scope": decision.value},
    )
    return True
