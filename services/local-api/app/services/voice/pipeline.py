"""VoiceHardwarePipeline — the real glue between hardware providers
(AudioInput/WakeWordDetector/VoiceActivityDetector/SpeechRecognitionProvider/
SpeechSynthesisProvider) and the already-real, hardware-agnostic
`VoiceConversationManager`. docs/voice-hardware/SETUP.md,
docs/phase-5/VOICE-ARCHITECTURE.md.

Before this, `VoiceConversationManager` only ever received already-
transcribed text via `POST /voice/sessions/{id}/utterances` — real, but
nothing in this build ever actually listened for a wake word or spoke a
response out loud. This module is the first thing that does: a single,
continuous loop over `AudioInput.stream()` that runs wake-word detection
until a real wake is detected, then records one bounded utterance (ended
by real silence-detection or a hard timeout — never unbounded),
transcribes it, feeds the text into the existing, unmodified
`VoiceConversationManager.submit_utterance`, and speaks the real
response back through `AudioOutput`.

`ActivationSource.WAKE_WORD` and `VoiceState.WAKE_DETECTED` have existed
in the voice contracts since Phase 5 but were never reachable — no real
wake-word detector existed to reach them (see manager.py's own comment
on `start_session`). This is the first real caller of either.
"""

from __future__ import annotations

import asyncio
import logging

from voice.core.enums import ActivationSource
from voice.providers.base import (
    AudioInput,
    AudioOutput,
    SpeechRecognitionProvider,
    VoiceActivityDetector,
    WakeWordDetector,
)
from voice.providers.base import SpeechSynthesisProvider as TTSProvider

from app.db.session import SessionLocal
from app.services.voice.manager import VoiceConversationManager

logger = logging.getLogger(__name__)

# A real utterance is bounded on both ends — never an unbounded recording
# loop (CLAUDE.md: "no unbounded loops, ever"). 12s covers a real spoken
# command with room to spare; 700ms of continuous silence after at least
# one speech chunk ends the recording early, so a short command doesn't
# wait out the full cap.
MAX_UTTERANCE_SECONDS = 12.0
TRAILING_SILENCE_SECONDS = 0.7
_CHUNK_SECONDS = 1280 / 16000  # openWakeWord/whisper's 16kHz, 1280-sample chunk


class VoiceHardwarePipeline:
    def __init__(
        self,
        *,
        audio_input: AudioInput,
        audio_output: AudioOutput,
        wake_word: WakeWordDetector,
        vad: VoiceActivityDetector,
        stt: SpeechRecognitionProvider,
        tts: TTSProvider,
        voice_manager: VoiceConversationManager,
        audio_device: str | None = None,
        max_utterance_seconds: float = MAX_UTTERANCE_SECONDS,
        trailing_silence_seconds: float = TRAILING_SILENCE_SECONDS,
    ) -> None:
        self._audio_input = audio_input
        self._audio_output = audio_output
        self._wake_word = wake_word
        self._vad = vad
        self._stt = stt
        self._tts = tts
        self._voice_manager = voice_manager
        self._audio_device = audio_device
        self._max_utterance_seconds = max_utterance_seconds
        self._trailing_silence_seconds = trailing_silence_seconds
        self._task: asyncio.Task | None = None
        self._stop_requested = False

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running():
            return
        self._stop_requested = False
        await self._audio_input.start(self._audio_device)
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_requested = True
        await self._audio_output.stop()
        await self._audio_input.stop()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        # A single continuous iteration over the one real stream — never
        # two independent calls to `AudioInput.stream()` racing (or, for
        # a scripted/mock stream, replaying) the same source. Wake-word
        # detection and utterance recording are two states of the same
        # loop, not two separate consumers.
        try:
            stream = self._audio_input.stream()
            async for chunk in stream:
                if self._stop_requested:
                    break
                activation = await self._wake_word.process_chunk(chunk)
                if activation.detected:
                    logger.info(
                        "[VOICE] Wake word detected: '%s' (confidence %.2f)",
                        activation.phrase,
                        activation.confidence,
                    )
                    await self._handle_wake_and_utterance(stream)
        except Exception:
            logger.exception("[VOICE] Hardware pipeline loop failed unexpectedly")

    async def _record_utterance(self, stream) -> list[bytes]:
        """Bounded recording, continuing the same stream the wake word
        was detected on: stops after real trailing silence (once speech
        has actually started) or the hard duration cap, whichever comes
        first — never waits forever."""
        chunks: list[bytes] = []
        elapsed = 0.0
        silence_run = 0.0
        heard_speech = False
        async for chunk in stream:
            if self._stop_requested:
                break
            chunks.append(chunk)
            elapsed += _CHUNK_SECONDS
            if self._vad.is_speech(chunk):
                heard_speech = True
                silence_run = 0.0
            else:
                silence_run += _CHUNK_SECONDS
            if heard_speech and silence_run >= self._trailing_silence_seconds:
                break
            if elapsed >= self._max_utterance_seconds:
                break
        return chunks

    async def _handle_wake_and_utterance(self, stream) -> None:
        chunks = await self._record_utterance(stream)
        if not chunks:
            return

        async def _replay():
            for chunk in chunks:
                yield chunk

        transcript_text = ""
        async for transcript in self._stt.transcribe(_replay()):
            if transcript.text.strip():
                transcript_text = transcript.text.strip()
        if not transcript_text:
            logger.info("[VOICE] Wake word triggered but nothing was transcribed — no command.")
            return

        async with SessionLocal() as db:
            session = await self._voice_manager.start_session(
                db, activation_source=ActivationSource.WAKE_WORD, audio_device=self._audio_device
            )
            try:
                result = await self._voice_manager.submit_utterance(
                    db, session.id, transcript_text
                )
                if result.response.should_speak and result.response.text:
                    await self._speak(result.response.text)
                await self._voice_manager.finish_response(db, session.id)
                if result.ended:
                    await self._voice_manager.end_session(db, session.id)
            except Exception:
                logger.exception(
                    "[VOICE] Failed to process wake-word utterance for session %s", session.id
                )
                await self._voice_manager.end_session(db, session.id)

    async def _speak(self, text: str) -> None:
        async def _audio():
            async for chunk in self._tts.synthesize(text):
                yield chunk

        await self._audio_output.play(_audio())
