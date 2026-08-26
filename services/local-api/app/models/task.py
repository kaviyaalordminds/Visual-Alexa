from __future__ import annotations

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import TaskState

from app.db.base import Base, IDMixin, TimestampMixin


class Task(Base, IDMixin, TimestampMixin):
    """docs/architecture/14-TASK-LIFECYCLE.md"""

    __tablename__ = "tasks"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(2000))
    state: Mapped[TaskState] = mapped_column(Enum(TaskState), default=TaskState.RECEIVED)
    max_steps: Mapped[int] = mapped_column(Integer)
    timeout_seconds: Mapped[int] = mapped_column(Integer)
    max_recovery_attempts: Mapped[int] = mapped_column(Integer)
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True)


class TaskStep(Base, IDMixin, TimestampMixin):
    __tablename__ = "task_steps"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    step_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[TaskState] = mapped_column(Enum(TaskState))
    tool_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
