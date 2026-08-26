"""Deterministic mock providers (brief §97/§115) — no audio hardware, no
real model, no network. Each implements the same `Protocol` as its
`NotConfigured*` counterpart in `voice.providers.base`, but returns seeded,
scripted results so tests can exercise the parts of the pipeline that only
run when a provider *is* configured (STT streaming, TTS playback,
wake-word detection, VAD) — mirroring
`vision.testing.fakes.FakeVisionProvider`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from voice.core.enums import Language
from voice.core.models import AudioDeviceInfo, TranscriptChunk, WakeWordActivation


class MockAudioInput:
    """docs/phase-5 §97. `seed_chunks` scripts what `stream()` yields;
    nothing here touches real audio hardware."""

    def __init__(self, devices: list[AudioDeviceInfo] | None = None) -> None:
        self.devices = devices or [
            AudioDeviceInfo(id="mock-mic", name="Mock Microphone", is_input=True, is_default=True)
        ]
        self.started = False
        self.chunks: list[bytes] = []

    def seed_chunks(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)

    async def start(self, device_id: str | None = None) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False

    async def stream(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            yield chunk

    async def list_devices(self) -> list[AudioDeviceInfo]:
        return list(self.devices)


class MockAudioOutput:
    """Records everything it "plays" in `played` so a test can assert on
    it; `stop()` mid-playback is what barge-in tests exercise."""

    def __init__(self, devices: list[AudioDeviceInfo] | None = None) -> None:
        self.devices = devices or [
            AudioDeviceInfo(id="mock-speaker", name="Mock Speaker", is_input=False, is_default=True)
        ]
        self.played: list[bytes] = []
        self.stopped = False
        self.paused = False

    async def play(self, audio_chunks: AsyncIterator[bytes]) -> None:
        self.stopped = False
        async for chunk in audio_chunks:
            if self.stopped:
                break
            self.played.append(chunk)

    async def stop(self) -> None:
        self.stopped = True

    async def pause(self) -> None:
        self.paused = True

    async def resume(self) -> None:
        self.paused = False

    async def list_devices(self) -> list[AudioDeviceInfo]:
        return list(self.devices)


class MockVAD:
    """Speech/silence is decided by a seeded set of chunks flagged as
    speech, never by inspecting audio content."""

    def __init__(self, speech_chunks: set[bytes] | None = None) -> None:
        self._speech_chunks = speech_chunks or set()

    def seed_speech(self, chunk: bytes) -> None:
        self._speech_chunks.add(chunk)

    def is_speech(self, audio_chunk: bytes) -> bool:
        return audio_chunk in self._speech_chunks


class MockWakeWord:
    """Reports a wake only for the one seeded chunk value — everything
    else is a non-activation, including silence and noise chunks a test
    seeds to prove false wakes don't happen (brief §102)."""

    def __init__(self, wake_chunk: bytes = b"WAKE", phrase: str = "Hey Veyra") -> None:
        self._wake_chunk = wake_chunk
        self._phrase = phrase

    async def process_chunk(self, audio_chunk: bytes) -> WakeWordActivation:
        if audio_chunk == self._wake_chunk:
            return WakeWordActivation(detected=True, phrase=self._phrase, confidence=0.95)
        return WakeWordActivation(detected=False)


class MockSTT:
    """Yields a scripted sequence of `TranscriptChunk`s regardless of the
    audio stream's actual bytes — the stream is still fully consumed, so
    tests exercising cancellation/backpressure against a real caller still
    behave realistically."""

    def __init__(self, transcripts: list[TranscriptChunk] | None = None) -> None:
        self.transcripts = transcripts or [
            TranscriptChunk(
                text="open chrome", is_final=True, confidence=0.95, language=Language.EN
            )
        ]

    def seed(self, transcripts: list[TranscriptChunk]) -> None:
        self.transcripts = transcripts

    async def transcribe(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        async for _ in audio_stream:
            pass
        for chunk in self.transcripts:
            yield chunk

    async def detect_language(self, text: str) -> Language:
        return Language.EN


class MockTTS:
    """Records every `synthesize()` call's text in `synthesized_text` so a
    test can assert what VEYRA "said" without any real audio being
    produced."""

    def __init__(self, audio_chunks: list[bytes] | None = None) -> None:
        self.audio_chunks = audio_chunks or [b"mock-audio-chunk"]
        self.stopped = False
        self.synthesized_text: list[str] = []

    async def synthesize(
        self, text: str, *, language: Language = Language.EN
    ) -> AsyncIterator[bytes]:
        self.synthesized_text.append(text)
        self.stopped = False
        for chunk in self.audio_chunks:
            if self.stopped:
                return
            yield chunk

    async def stop(self) -> None:
        self.stopped = True
