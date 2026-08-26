"""Provider-independent audio/STT/TTS/wake-word abstractions.
docs/phase-5/VOICE-ARCHITECTURE.md, brief §5-19/§32-41.

No real provider ships in Phase 5 (docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md
§3) for the same reason Phase 3 shipped no real vision model: every
`Protocol` here gets exactly one real, honest, non-raising, no-hardware/
no-network `NotConfigured*` implementation, mirroring
`vision.core.vision_provider.NotConfiguredVisionProvider`. A future
sounddevice/local-STT/cloud-STT/TTS backend implements the same Protocol
in a lazy-imported `voice/providers/real.py` (see pyproject.toml's `audio`
extra) without any caller changing.

Cloud STT/TTS gating (provider-enabled + privacy policy + network + user
config, brief §17-19/§54) is enforced by the caller
(`app/services/voice`), never by a provider implementation itself — these
Protocols have no notion of "cloud" beyond whatever a concrete provider
happens to be.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from voice.core.enums import Language
from voice.core.models import AudioDeviceInfo, TranscriptChunk, WakeWordActivation


class AudioInput(Protocol):
    """docs/phase-5 §5-6. `stream()` yields raw PCM chunks; a caller (VAD,
    wake-word, STT) never touches an OS handle directly."""

    async def start(self, device_id: str | None = None) -> None: ...
    async def stop(self) -> None: ...
    def stream(self) -> AsyncIterator[bytes]: ...
    async def list_devices(self) -> list[AudioDeviceInfo]: ...


class AudioOutput(Protocol):
    """docs/phase-5 §32-41/§63-64. `stop()` must be safe to call at any
    time — barge-in depends on it interrupting playback immediately."""

    async def play(self, audio_chunks: AsyncIterator[bytes]) -> None: ...
    async def stop(self) -> None: ...
    async def pause(self) -> None: ...
    async def resume(self) -> None: ...
    async def list_devices(self) -> list[AudioDeviceInfo]: ...


class VoiceActivityDetector(Protocol):
    """docs/phase-5 §7. Pure classification over one chunk — any temporal
    smoothing is internal to the implementation, never the caller's job."""

    def is_speech(self, audio_chunk: bytes) -> bool: ...


class WakeWordDetector(Protocol):
    """docs/phase-5 §8-10. Below-threshold activations are filtered by the
    implementation itself — callers only ever see a real `detected=True`
    result or `detected=False`, never a confidence they must re-check."""

    async def process_chunk(self, audio_chunk: bytes) -> WakeWordActivation: ...


class SpeechRecognitionProvider(Protocol):
    """docs/phase-5 §15-19. `transcribe` streams partial and final
    `TranscriptChunk`s from a raw audio stream — provider-agnostic; the
    LOCAL/CLOUD/AUTO decision (and the privacy/network/config gate before
    any CLOUD call) lives in the caller, never here."""

    def transcribe(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[TranscriptChunk]: ...
    async def detect_language(self, text: str) -> Language: ...


class SpeechSynthesisProvider(Protocol):
    """docs/phase-5 §32-41. `synthesize` streams audio chunks so playback
    can start before the full utterance is generated (brief §72 — do not
    wait for the full response before speaking)."""

    def synthesize(
        self, text: str, *, language: Language = Language.EN
    ) -> AsyncIterator[bytes]: ...
    async def stop(self) -> None: ...


class NotConfiguredAudioInput:
    """The one `AudioInput` Phase 5 ships. Never raises — behaves as if no
    microphone exists, matching this environment's own reality
    (docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §1)."""

    async def start(self, device_id: str | None = None) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def stream(self) -> AsyncIterator[bytes]:
        return
        yield b""  # pragma: no cover - unreachable; makes this an async generator

    async def list_devices(self) -> list[AudioDeviceInfo]:
        return []


class NotConfiguredAudioOutput:
    """The one `AudioOutput` Phase 5 ships. Every call is a no-op — there
    is no speaker to play to in this environment."""

    async def play(self, audio_chunks: AsyncIterator[bytes]) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def pause(self) -> None:
        return None

    async def resume(self) -> None:
        return None

    async def list_devices(self) -> list[AudioDeviceInfo]:
        return []


class NotConfiguredVAD:
    """Reports silence unconditionally — never fabricates a speech
    detection it cannot actually make."""

    def is_speech(self, audio_chunk: bytes) -> bool:
        return False


class NotConfiguredWakeWord:
    """Never reports a wake — no false activations, ever."""

    async def process_chunk(self, audio_chunk: bytes) -> WakeWordActivation:
        return WakeWordActivation(detected=False)


class NotConfiguredSTT:
    """Yields nothing — no local/cloud STT backend is configured."""

    async def transcribe(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        return
        yield TranscriptChunk(text="", is_final=True)  # pragma: no cover

    async def detect_language(self, text: str) -> Language:
        return Language.UNKNOWN


class NotConfiguredTTS:
    """Synthesizes silence — no local/cloud TTS backend is configured."""

    async def synthesize(
        self, text: str, *, language: Language = Language.EN
    ) -> AsyncIterator[bytes]:
        return
        yield b""  # pragma: no cover

    async def stop(self) -> None:
        return None
