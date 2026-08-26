"""POST/GET /tasks. docs/architecture/14-TASK-LIFECYCLE.md.

Phase 1 creates a task row in RECEIVED state with a mandatory TaskBudget —
CLAUDE.md: 'No unbounded loops, ever.' No live Task Runtime advances a task
past RECEIVED in Phase 1 (no planner/executor exists yet); this endpoint
proves the data model and budget validation work end-to-end.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import TaskBudget, TaskState

from app.api.deps import get_or_create_local_user
from app.db.session import get_session
from app.models.task import Task as TaskRow

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskOut(BaseModel):
    id: str
    description: str
    state: TaskState
    max_steps: int
    timeout_seconds: int
    max_recovery_attempts: int
    correlation_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    description: str
    conversation_id: str | None = None
    budget: TaskBudget


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
        correlation_id=str(uuid4()),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return TaskOut.model_validate(row)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)) -> TaskOut:
    result = await session.execute(select(TaskRow).where(TaskRow.id == task_id))
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown task '{task_id}'.")
    return TaskOut.model_validate(row)
