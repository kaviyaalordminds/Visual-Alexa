from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IDMixin, TimestampMixin


class Integration(Base, IDMixin, TimestampMixin):
    """docs/architecture/11-INTEGRATIONS.md — official-API adapters only.
    No integration is connected in Phase 1."""

    __tablename__ = "integrations"

    provider: Mapped[str] = mapped_column(String(100))  # e.g. "gmail"
    auth_method: Mapped[str] = mapped_column(String(50))  # OAUTH2 | API_KEY | NONE
    connected: Mapped[bool] = mapped_column(default=False)
    credentials_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
