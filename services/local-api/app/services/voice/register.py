"""Builds the process-wide `VoiceConversationManager` singleton at
startup — mirrors `app/services/agent/register.py`'s own
`AgentOrchestrator` singleton pattern exactly.

`build_and_start_voice_pipeline` additionally builds whichever real
hardware providers (wake-word/STT/TTS/audio I/O) are configured
(`app/core/config.py`) and, if a full real pipeline loaded, starts it —
see `app/services/voice/pipeline.py`. Every failure here is recorded as
a health-check reason via `subsystem_health.py`'s real-status registry,
never a startup crash — voice is an optional subsystem exactly like AI/
Vision/IoT.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.subsystem_health import (
    VoiceComponentStatus,
    record_voice_stt_status,
    record_voice_tts_status,
    record_voice_wake_word_status,
)
from app.services.voice.manager import VoiceConversationManager
from app.services.voice.pipeline import VoiceHardwarePipeline

logger = logging.getLogger(__name__)

_manager: VoiceConversationManager | None = None
_pipeline: VoiceHardwarePipeline | None = None


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


def get_voice_pipeline() -> VoiceHardwarePipeline | None:
    """`None` when no real hardware pipeline is running — a real,
    honest possibility (nothing configured, a package/model missing, or
    no audio hardware present), not an error to raise on."""
    return _pipeline


async def build_and_start_voice_pipeline(settings: Settings) -> None:
    from voice.providers.base import NotConfiguredSTT, NotConfiguredTTS, NotConfiguredWakeWord
    from voice.providers.real import (
        EnergyVAD,
        OpenWakeWordDetector,
        PiperTTSProvider,
        SounddeviceAudioInput,
        SounddeviceAudioOutput,
        VoiceProviderUnavailableError,
        WhisperSTTProvider,
    )

    wake_word: object = NotConfiguredWakeWord()
    wake_word_ready = False
    if settings.wake_word_provider == "openwakeword":
        try:
            wake_word = OpenWakeWordDetector(
                settings.wake_word_model, threshold=settings.wake_word_threshold
            )
            wake_word_ready = True
            record_voice_wake_word_status(
                VoiceComponentStatus(
                    True, f"openWakeWord ('{settings.wake_word_model}') real and loaded."
                )
            )
        except VoiceProviderUnavailableError as exc:
            record_voice_wake_word_status(VoiceComponentStatus(False, str(exc)))
    elif settings.wake_word_provider:
        record_voice_wake_word_status(
            VoiceComponentStatus(
                False, f"Unknown wake-word provider '{settings.wake_word_provider}'."
            )
        )

    stt: object = NotConfiguredSTT()
    stt_ready = False
    if settings.stt_provider == "whisper_cpp":
        try:
            stt = WhisperSTTProvider(
                settings.whisper_model, models_dir=settings.whisper_models_dir or None
            )
            stt_ready = True
            record_voice_stt_status(
                VoiceComponentStatus(
                    True, f"whisper.cpp ('{settings.whisper_model}') real and loaded."
                )
            )
        except VoiceProviderUnavailableError as exc:
            record_voice_stt_status(VoiceComponentStatus(False, str(exc)))
    elif settings.stt_provider:
        record_voice_stt_status(
            VoiceComponentStatus(False, f"Unknown STT provider '{settings.stt_provider}'.")
        )

    tts: object = NotConfiguredTTS()
    tts_ready = False
    if settings.tts_provider == "piper":
        if not settings.piper_voice_model_path:
            record_voice_tts_status(
                VoiceComponentStatus(
                    False, "tts_provider='piper' but no piper_voice_model_path is configured."
                )
            )
        else:
            try:
                tts = PiperTTSProvider(settings.piper_voice_model_path)
                tts_ready = True
                record_voice_tts_status(
                    VoiceComponentStatus(
                        True, f"Piper ('{settings.piper_voice_model_path}') real and loaded."
                    )
                )
            except VoiceProviderUnavailableError as exc:
                record_voice_tts_status(VoiceComponentStatus(False, str(exc)))
    elif settings.tts_provider:
        record_voice_tts_status(
            VoiceComponentStatus(False, f"Unknown TTS provider '{settings.tts_provider}'.")
        )

    if not (wake_word_ready and stt_ready and tts_ready):
        # A partial real setup (e.g. TTS loaded but no wake word) is
        # honestly reported by compute_voice_status above — but the
        # hardware *listen loop* needs all three to do anything useful,
        # so it simply doesn't start rather than half-running.
        return

    try:
        audio_input = SounddeviceAudioInput()
        audio_output = SounddeviceAudioOutput()
    except VoiceProviderUnavailableError as exc:
        logger.info("[VOICE] Real wake-word/STT/TTS all loaded, but no audio hardware: %s", exc)
        return

    global _pipeline
    _pipeline = VoiceHardwarePipeline(
        audio_input=audio_input,
        audio_output=audio_output,
        wake_word=wake_word,  # type: ignore[arg-type]
        vad=EnergyVAD(),
        stt=stt,  # type: ignore[arg-type]
        tts=tts,  # type: ignore[arg-type]
        voice_manager=get_voice_manager(),
        audio_device=settings.audio_input_device or None,
    )
    await _pipeline.start()
    logger.info(
        "[VOICE] Real hardware pipeline started — wake word '%s', whisper.cpp '%s', Piper voice.",
        settings.wake_word_model,
        settings.whisper_model,
    )


async def stop_voice_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        await _pipeline.stop()
        _pipeline = None
