from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import Confidence, ErrorCategory, RiskLevel, TaskPriority, TaskState

from app.db.base import Base, IDMixin, TimestampMixin


class Task(Base, IDMixin, TimestampMixin):
    """docs/architecture/14-TASK-LIFECYCLE.md. Phase 4
    (docs/phase-4/TASK-ENGINE.md) extends this table additively with the
    fields the AgentOrchestrator needs — no parallel table, per
    docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §9."""

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

    # --- Phase 4 additions ---
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    normalized_goal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.NORMAL)
    max_replans: Mapped[int] = mapped_column(Integer, default=3)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel), nullable=True)
    requires_confirmation: Mapped[bool] = mapped_column(default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Phase 5 addition (docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §6): the
    # orchestrator already knows *why* a task failed at the moment it fails
    # (an ErrorCategory), but previously only persisted the free-text
    # `failure_reason`. ResponseGenerator needs the real category — e.g. to
    # tell CAPABILITY_UNAVAILABLE apart from an ordinary failure (brief
    # §85-86) — so it's now persisted alongside the reason instead of lost.
    failure_category: Mapped[ErrorCategory | None] = mapped_column(
        Enum(ErrorCategory), nullable=True
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Not named `metadata` — reserved on SQLAlchemy declarative models.
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class TaskStep(Base, IDMixin, TimestampMixin):
    __tablename__ = "task_steps"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    step_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[TaskState] = mapped_column(Enum(TaskState))
    tool_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)

    # --- Phase 4 additions ---
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    intent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_outcome: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    actual_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel), nullable=True)
    confidence: Mapped[Confidence | None] = mapped_column(Enum(Confidence), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # References/summaries only — never raw screenshot bytes, continuing
    # Phase 3's own discipline (docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §7).
    observation_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    observation_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
