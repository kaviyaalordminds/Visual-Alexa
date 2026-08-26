from __future__ import annotations

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from veyra_contracts import EvidenceTier, RiskLevel, ToolResultStatus

from app.db.base import Base, IDMixin, TimestampMixin


class AuditLog(Base, IDMixin, TimestampMixin):
    """docs/security/06-AUDIT-LOGGING.md — written for every tool
    execution, success or failure, every risk tier."""

    __tablename__ = "audit_logs"

    correlation_id: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tool_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(String(200))
    target: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    permission_grant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    result_status: Mapped[ToolResultStatus] = mapped_column(Enum(ToolResultStatus))
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_tier_used: Mapped[EvidenceTier | None] = mapped_column(
        Enum(EvidenceTier), nullable=True
    )
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
