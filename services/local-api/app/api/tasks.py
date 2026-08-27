"""POST/GET /tasks + Phase 4 execution endpoints.
docs/architecture/14-TASK-LIFECYCLE.md, docs/phase-4/TASK-ENGINE.md.

Phase 1 created a task row in RECEIVED state with a mandatory
TaskBudget — CLAUDE.md: 'No unbounded loops, ever.' Phase 4 adds the
actual execution trigger (`/run`) plus the cooperative controls a
running task needs (`/cancel`, `/confirm`) and read-only progress
endpoints (`/steps`) — see docs/phase-4/TASK-API.md.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import PermissionDecision, TaskBudget, TaskState

from app.api.deps import get_or_create_local_user
from app.db.session import SessionLocal, get_session
from app.models.task import Task as TaskRow
from app.models.task import TaskStep as TaskStepRow
from app.services.agent.confirmation_actions import (
    NoPendingConfirmationError,
    apply_confirmation_decision,
)
from app.services.agent.orchestrator import request_cancellation, request_pause
from app.services.agent.register import get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Holds strong references to in-flight background run/resume tasks so
# they aren't garbage-collected mid-execution (asyncio only holds a weak
# reference internally) — each entry removes itself on completion.
_background_tasks: set[asyncio.Task] = set()


def _spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

_ACTIVE_STATES = frozenset(
    {
        TaskState.RECEIVED,
        TaskState.UNDERSTANDING,
        TaskState.PLANNING,
        TaskState.WAITING_PERMISSION,
        TaskState.EXECUTING,
        TaskState.OBSERVING,
        TaskState.VERIFYING,
        TaskState.RECOVERING,
        TaskState.WAITING_USER,
        TaskState.PAUSED,
    }
)


class TaskOut(BaseModel):
    id: str
    description: str
    state: TaskState
    max_steps: int
    timeout_seconds: int
    max_recovery_attempts: int
    correlation_id: str
    created_at: datetime
    current_step: int
    total_steps: int
    requires_confirmation: bool
    failure_reason: str | None
    result: dict | None

    model_config = {"from_attributes": True}


class TaskStepOut(BaseModel):
    id: str
    step_number: int
    state: TaskState
    tool_id: str | None
    description: str | None
    arguments: dict
    risk_level: str | None
    retry_count: int
    error: dict | None
    actual_result: dict | None

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    description: str
    conversation_id: str | None = None
    budget: TaskBudget


async def _get_task_or_404(task_id: str, session: AsyncSession) -> TaskRow:
    result = await session.execute(select(TaskRow).where(TaskRow.id == task_id))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_id}'.")
    return row


@router.get("", response_model=list[TaskOut])
async def list_tasks(session: AsyncSession = Depends(get_session)) -> list[TaskOut]:
    result = await session.execute(select(TaskRow))
    return [TaskOut.model_validate(row) for row in result.scalars()]


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(body: TaskCreate, session: AsyncSession = Depends(get_session)) -> TaskOut:
    user = await get_or_create_local_user(session)
    row = TaskRow(
        user_id=user.id,
        conversation_id=body.conversation_id,
        description=body.description,
        state=TaskState.RECEIVED,
        max_steps=body.budget.max_steps,
        timeout_seconds=body.budget.timeout_seconds,
        max_recovery_attempts=body.budget.max_recovery_attempts,
        max_replans=body.budget.max_replans,
        correlation_id=str(uuid4()),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return TaskOut.model_validate(row)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    return TaskOut.model_validate(await _get_task_or_404(task_id, session))


@router.get("/{task_id}/steps", response_model=list[TaskStepOut])
async def get_task_steps(
    task_id: str, session: AsyncSession = Depends(get_session)
) -> list[TaskStepOut]:
    await _get_task_or_404(task_id, session)
    result = await session.execute(
        select(TaskStepRow).where(TaskStepRow.task_id == task_id).order_by(TaskStepRow.step_number)
    )
    return [TaskStepOut.model_validate(row) for row in result.scalars()]


async def _run_in_background(task_id: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(TaskRow).where(TaskRow.id == task_id))
        row = result.scalars().first()
        if row is None:
            return
        try:
            await get_orchestrator().run(session, row)
        except Exception:
            logger.exception("agent.task_run_failed", extra={"task_id": task_id})


@router.post("/{task_id}/run", response_model=TaskOut, status_code=202)
async def run_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    row = await _get_task_or_404(task_id, session)
    if row.state != TaskState.RECEIVED:
        raise HTTPException(
            status_code=409, detail=f"Task is already '{row.state.value}', not RECEIVED."
        )
    _spawn_background(_run_in_background(task_id))
    return TaskOut.model_validate(row)


@router.post("/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    """docs/phase-4/AGENT-ARCHITECTURE.md §24 — cooperative: sets a signal
    the running orchestrator checks between steps. A task already
    terminal is a no-op, not an error (idempotent 'stop' semantics)."""
    row = await _get_task_or_404(task_id, session)
    if row.state in _ACTIVE_STATES:
        request_cancellation(task_id)
    return TaskOut.model_validate(row)


@router.post("/{task_id}/pause", response_model=TaskOut)
async def pause_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    """docs/phase-5/BARGE-IN.md — the same cooperative-signal pattern as
    `/cancel`: sets a signal the running orchestrator checks between
    steps. A task not currently active is a no-op, not an error."""
    row = await _get_task_or_404(task_id, session)
    if row.state in _ACTIVE_STATES:
        request_pause(task_id)
    return TaskOut.model_validate(row)


async def _resume_after_pause_in_background(task_id: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(TaskRow).where(TaskRow.id == task_id))
        row = result.scalars().first()
        if row is None:
            return
        try:
            await get_orchestrator().resume_after_pause(session, row)
        except Exception:
            logger.exception("agent.task_resume_after_pause_failed", extra={"task_id": task_id})


@router.post("/{task_id}/resume", response_model=TaskOut)
async def resume_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    """docs/phase-5/BARGE-IN.md — resumes the *same* remaining plan a
    PAUSED task was holding, never a full replan. Nothing to authorize
    here (unlike `/confirm`) — pausing was never a security gate, just a
    cooperative "wait a moment"."""
    row = await _get_task_or_404(task_id, session)
    if row.state != TaskState.PAUSED:
        raise HTTPException(status_code=409, detail=f"Task is '{row.state.value}', not PAUSED.")
    _spawn_background(_resume_after_pause_in_background(task_id))
    return TaskOut.model_validate(row)


class ConfirmRequest(BaseModel):
    decision: PermissionDecision = PermissionDecision.ALLOW_ONCE


@router.post("/{task_id}/confirm", response_model=TaskOut)
async def confirm_task(
    task_id: str, body: ConfirmRequest, session: AsyncSession = Depends(get_session)
) -> TaskOut:
    """docs/phase-4/CONFIRMATION.md — creates the exact, time-limited
    PermissionGrant the paused step needs, then resumes execution of the
    same plan (in the background, like /run) rather than replanning."""
    row = await _get_task_or_404(task_id, session)
    try:
        resumed = await apply_confirmation_decision(session, row, body.decision)
    except NoPendingConfirmationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if resumed:
        _spawn_background(_resume_in_background(task_id))
    return TaskOut.model_validate(row)


async def _resume_in_background(task_id: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(TaskRow).where(TaskRow.id == task_id))
        row = result.scalars().first()
        if row is None:
            return
        try:
            await get_orchestrator().resume_after_confirmation(session, row)
        except Exception:
            logger.exception("agent.task_resume_failed", extra={"task_id": task_id})
