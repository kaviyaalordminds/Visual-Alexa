from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import AuthMethod, IntegrationState

from app.db.base import Base, IDMixin, TimestampMixin


class Integration(Base, IDMixin, TimestampMixin):
    """docs/architecture/11-INTEGRATIONS.md — official-API adapters only.
    Phase 7 (docs/phase-7/INTEGRATION-ARCHITECTURE.md) adds `name`/
    `state`/`scopes`/`connected_at`/`last_health_check_at` additively and
    makes `auth_method` a real enum (the column was already always
    populated with one of its three values, never enforced)."""

    __tablename__ = "integrations"

    provider: Mapped[str] = mapped_column(String(100))  # e.g. "gmail"
    auth_method: Mapped[AuthMethod] = mapped_column(Enum(AuthMethod))
    connected: Mapped[bool] = mapped_column(default=False)
    credentials_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # --- Phase 7 additions ---
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    state: Mapped[IntegrationState] = mapped_column(
        Enum(IntegrationState), default=IntegrationState.CONNECT_REQUIRED
    )
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
