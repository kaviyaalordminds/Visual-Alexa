"""Binds veyra-voice's provider-independent pipeline to the real,
already-existing Task Engine (Phase 4). docs/phase-5/CONVERSATION.md.

This is the only place the two packages meet: `voice.core` has no DB
access and no knowledge of `AgentOrchestrator`; `app/services/agent` has
no knowledge of audio, wake words, or language detection. Everything here
is a caller of both, never a reimplementation of either.
"""

from __future__ import annotations

from app.services.voice.manager import VoiceConversationManager, VoiceTurnResult
from app.services.voice.register import get_voice_manager, init_voice_manager

__all__ = [
    "VoiceConversationManager",
    "VoiceTurnResult",
    "get_voice_manager",
    "init_voice_manager",
]
