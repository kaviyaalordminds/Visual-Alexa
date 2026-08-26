"""VoiceSessionRow — DB-persisted voice session metadata.
docs/phase-5/VOICE-ARCHITECTURE.md, brief §12.

Deliberately minimal: no raw audio column, no transcript column — audio is
never retained by default (brief §50-51) and transcripts reuse the
existing `Conversation`/`Message` tables rather than a new one (see
docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §8). This table exists so a
voice session survives a process restart and is inspectable via the API,
mirroring `Task`'s own persistence. Named `VoiceSessionRow` (not
`VoiceSession`) to avoid colliding with `voice.core.models.VoiceSession`,
the in-memory pydantic shape `VoiceConversationManager` actually operates
on — the same `Row` suffix convention `app/services/agent/orchestrator.py`
uses for `Task`/`TaskStep`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from voice.core.enums import ActivationSource, Language, VoiceState

from app.db.base import Base, IDMixin, TimestampMixin


class VoiceSessionRow(Base, IDMixin, TimestampMixin):
    __tablename__ = "voice_sessions"

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[Language] = mapped_column(Enum(Language), default=Language.UNKNOWN)
    status: Mapped[VoiceState] = mapped_column(Enum(VoiceState), default=VoiceState.IDLE)
    active_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    activation_source: Mapped[ActivationSource] = mapped_column(
        Enum(ActivationSource), default=ActivationSource.API
    )
    audio_device: Mapped[str | None] = mapped_column(String(200), nullable=True)
