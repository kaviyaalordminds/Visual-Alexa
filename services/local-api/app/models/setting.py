from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IDMixin, TimestampMixin


class SystemSetting(Base, IDMixin, TimestampMixin):
    """Conservative-by-default settings — see docs/security/05-DATA-PROTECTION.md
    §3. The initial migration seeds mic/screen/devices/remote all OFF."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(200), unique=True)
    value: Mapped[dict] = mapped_column(JSON)
