from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import MemoryCategory

from app.db.base import Base, IDMixin, TimestampMixin


class Memory(Base, IDMixin, TimestampMixin):
    """docs/architecture/09-MEMORY.md — user-controlled, inspectable,
    editable, deletable, auditable. No hidden memory."""

    __tablename__ = "memories"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    category: Mapped[MemoryCategory] = mapped_column(Enum(MemoryCategory))
    key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Workflow(Base, IDMixin, TimestampMixin):
    """User-defined trigger -> steps automation (distinct from
    WorkflowMemory aliases stored in Memory — see
    docs/architecture/09-MEMORY.md §4). No execution engine in Phase 1."""

    __tablename__ = "workflows"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    trigger_phrase: Mapped[str | None] = mapped_column(String(500), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(default=True)
