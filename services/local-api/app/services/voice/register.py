"""Builds the process-wide `VoiceConversationManager` singleton at
startup — mirrors `app/services/agent/register.py`'s own
`AgentOrchestrator` singleton pattern exactly.
"""

from __future__ import annotations

from app.services.voice.manager import VoiceConversationManager

_manager: VoiceConversationManager | None = None


def init_voice_manager() -> VoiceConversationManager:
    global _manager
    _manager = VoiceConversationManager()
    return _manager


def get_voice_manager() -> VoiceConversationManager:
    if _manager is None:
        raise RuntimeError(
            "VoiceConversationManager was not initialized — init_voice_manager() must "
            "run at process startup (see app/main.py)."
        )
    return _manager
