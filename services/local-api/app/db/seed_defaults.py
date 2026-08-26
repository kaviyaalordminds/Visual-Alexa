"""Shared default SystemSetting values. Single source of truth used by both
the Alembic seed migration (database/migrations/versions/..._seed_...py)
and the test suite, so they can never drift apart.
See docs/security/05-DATA-PROTECTION.md §3.
"""

from __future__ import annotations

DEFAULT_SETTINGS: dict[str, object] = {
    "microphone.enabled": False,
    "screen_observation.enabled": False,
    "external_devices.enabled": False,
    "remote_access.enabled": False,
    "ai.mode": None,
    "ai.configured": False,
    "voice.configured": False,
    "vision.configured": False,
    "computer_control.enabled": False,
    "security.active": True,
    # --- Phase 5: voice intelligence engine (brief §104-106) ---
    # docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §8. The brief lists
    # "wake_word.mode" and "voice.mode" as separate keys describing the
    # same WakeWordMode value — consolidated into the one "voice.mode" key
    # here, the same deliberate-consolidation approach
    # VoiceSession.status took for a similar brief-level duplication.
    "voice.enabled": False,
    "voice.input_device": None,
    "voice.output_device": None,
    "voice.mode": "WAKE_WORD_ONLY",
    "wake_word.enabled": False,
    "wake_word.phrase": "Hey Veyra",
    "wake_word.sensitivity": 0.5,
    "stt.provider": None,
    "stt.mode": "LOCAL",
    "tts.provider": None,
    "tts.voice": None,
    "tts.speed": 1.0,
    "tts.pitch": 1.0,
    "cloud_fallback.enabled": False,
    "audio.noise_suppression": True,
    "audio.echo_cancellation": True,
}
