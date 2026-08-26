from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import ConfirmationPolicy, PermissionDecision, RiskLevel, ToolCategory

from app.db.base import Base, IDMixin, TimestampMixin


class Tool(Base, IDMixin, TimestampMixin):
    """Mirrors veyra_contracts.ToolDefinition. See
    docs/architecture/04-TOOL-ARCHITECTURE.md. Registering a tool means
    inserting (or upserting) a row here via ToolRegistry."""

    __tablename__ = "tools"

    tool_id: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000))
    category: Mapped[ToolCategory] = mapped_column(Enum(ToolCategory))
    input_schema: Mapped[dict] = mapped_column(JSON)
    output_schema: Mapped[dict] = mapped_column(JSON)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    required_permission: Mapped[str] = mapped_column(String(200))
    confirmation_policy: Mapped[ConfirmationPolicy] = mapped_column(
        Enum(ConfirmationPolicy), default=ConfirmationPolicy.NEVER
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    cancellable: Mapped[bool] = mapped_column(default=True)
    verification_strategy: Mapped[str] = mapped_column(String(500), default="none")


class Permission(Base, IDMixin, TimestampMixin):
    """A permission *scope* that can be granted. Distinct from
    PermissionGrant (the actual grant record) — see
    docs/security/02-PERMISSION-MODEL.md."""

    __tablename__ = "permissions"

    scope_key: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(String(1000))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))


class PermissionGrant(Base, IDMixin, TimestampMixin):
    __tablename__ = "permission_grants"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    tool_id: Mapped[str] = mapped_column(String(200))
    target: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    scope: Mapped[PermissionDecision] = mapped_column(Enum(PermissionDecision))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
