from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IDMixin, TimestampMixin


class Application(Base, IDMixin, TimestampMixin):
    """A known application on the local machine (future: populated by an
    application-discovery tool — docs/architecture/05-COMPUTER-CONTROL.md
    ApplicationController). No discovery runs in Phase 1."""

    __tablename__ = "applications"

    name: Mapped[str] = mapped_column(String(200))
    executable_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    identifier: Mapped[str] = mapped_column(String(200), unique=True)
