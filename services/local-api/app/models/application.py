from __future__ import annotations

from sqlalchemy import JSON, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import RiskLevel

from app.db.base import Base, IDMixin, TimestampMixin


class Application(Base, IDMixin, TimestampMixin):
    """The Application Registry. docs/phase-2/APPLICATION-CONTROL.md,
    docs/phase-2 §20. `executable_path` is Phase 1's original column,
    kept as a last-known-good cache only — computer_control.registry
    always re-resolves via `executable_candidates` (PATH/well-known-dir
    search) at launch time rather than trusting a stored path, per
    docs/phase-2 §6.2 'do not assume paths.'"""

    __tablename__ = "applications"

    name: Mapped[str] = mapped_column(String(200))
    executable_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    identifier: Mapped[str] = mapped_column(String(200), unique=True)

    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    executable_candidates: Mapped[list[str]] = mapped_column(JSON, default=list)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    install_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.MODERATE)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_strategy: Mapped[str] = mapped_column(
        String(200), default="process_and_window_detection"
    )
