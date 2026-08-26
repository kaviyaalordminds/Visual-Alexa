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
from veyra_contracts import PermissionDecision, TaskState

from app.api.deps import get_or_create_local_user
from app.models.task import Task as TaskRow
from app.models.tool import PermissionGrant as PermissionGrantRow
from app.services.agent.state_machine import TaskStateMachine

# docs/phase-4/CONFIRMATION.md §22 — a confirm-created grant is
# single-use and time-limited, never a standing ALWAYS_ALLOW.
CONFIRMATION_GRANT_TTL_SECONDS = 300


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
        return False

    user = await get_or_create_local_user(session)
    pending_risk = (task.result or {}).get("pending_risk_level")
    grant = PermissionGrantRow(
        user_id=user.id,
        tool_id=(task.result or {}).get("pending_tool_id"),
        target=(task.result or {}).get("pending_target"),
        risk_level=pending_risk,
        scope=decision,
        granted_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(seconds=CONFIRMATION_GRANT_TTL_SECONDS),
    )
    session.add(grant)
    await session.commit()
    await session.refresh(task)
    return True
