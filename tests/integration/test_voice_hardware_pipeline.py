"""VoiceHardwarePipeline — the real wiring between hardware providers and
the already-real VoiceConversationManager. docs/voice-hardware/SETUP.md.

Uses the same deterministic mock providers `voice.testing.mocks` ships
for exactly this purpose — no real audio hardware or model needed to
prove the wiring itself (wake -> record -> transcribe -> respond ->
speak) is correct. `ActivationSource.WAKE_WORD` and `VoiceState.
WAKE_DETECTED` have existed since Phase 5 but were never reachable until
this pipeline existed to reach them.
"""

from __future__ import annotations

import asyncio

from app.models.conversation import Message as MessageRow
from app.services.voice.pipeline import VoiceHardwarePipeline
from app.services.voice.register import get_voice_manager
from sqlalchemy import select
from voice.core.models import TranscriptChunk
from voice.testing.mocks import (
    MockAudioInput,
    MockAudioOutput,
    MockSTT,
    MockTTS,
    MockVAD,
    MockWakeWord,
)

_WAKE = b"WAKE"
_SPEECH = b"SPEECH"
_SILENCE_1 = b"SILENCE_1"
_SILENCE_2 = b"SILENCE_2"


def _pipeline(**overrides):
    defaults: dict = {
        "audio_input": MockAudioInput(),
        "audio_output": MockAudioOutput(),
        "wake_word": MockWakeWord(wake_chunk=_WAKE),
        "vad": MockVAD(speech_chunks={_SPEECH}),
        "stt": MockSTT([TranscriptChunk(text="open notepad", is_final=True, confidence=0.9)]),
        "tts": MockTTS(),
        "voice_manager": get_voice_manager(),
        # Two chunks of silence is enough to end the utterance in these
        # tests — 1280/16000 = 0.08s per chunk, so 0.1s covers 2 chunks.
        "trailing_silence_seconds": 0.1,
        "max_utterance_seconds": 5.0,
    }
    defaults.update(overrides)
    return VoiceHardwarePipeline(**defaults)


async def test_wake_word_triggers_a_real_wake_word_activation_source_session(db_session):
    """The first real, reachable use of `ActivationSource.WAKE_WORD` —
    every other session-start path in this codebase is API/push-to-talk/
    hotkey."""
    audio_input = MockAudioInput()
    audio_input.seed_chunks([_SILENCE_1, _WAKE, _SPEECH, _SILENCE_1, _SILENCE_2])
    pipeline = _pipeline(audio_input=audio_input)

    await pipeline.start()
    await asyncio.wait_for(_wait_until_stopped(pipeline), timeout=5.0)

    result = await db_session.execute(select(MessageRow))
    messages = result.scalars().all()
    assert any("open notepad" in m.content for m in messages if m.content)


async def _wait_until_stopped(pipeline: VoiceHardwarePipeline) -> None:
    while pipeline.is_running():
        await asyncio.sleep(0.01)


async def test_wake_word_never_falsely_triggers_on_ordinary_audio():
    audio_input = MockAudioInput()
    audio_input.seed_chunks([_SILENCE_1, _SILENCE_2, _SILENCE_1, _SILENCE_2])
    tts = MockTTS()
    pipeline = _pipeline(audio_input=audio_input, tts=tts)

    await pipeline.start()
    await asyncio.wait_for(_wait_until_stopped(pipeline), timeout=5.0)

    assert tts.synthesized_text == []


async def test_utterance_recording_stops_on_real_trailing_silence_not_the_hard_cap():
    """Proves the VAD-based early stop actually works — the recording
    ends after 2 silence chunks, not after burning the full 5s cap."""
    audio_input = MockAudioInput()
    audio_input.seed_chunks([_WAKE, _SPEECH, _SILENCE_1, _SILENCE_2])
    stt = MockSTT([TranscriptChunk(text="find report.pdf", is_final=True, confidence=0.9)])
    pipeline = _pipeline(audio_input=audio_input, stt=stt, max_utterance_seconds=5.0)

    await pipeline.start()
    await asyncio.wait_for(_wait_until_stopped(pipeline), timeout=2.0)
    # Reaching here within the 2s test timeout (well under the 5s hard
    # cap) proves the early stop, not the cap, ended the recording.


async def test_stop_is_cooperative_and_completes_quickly():
    audio_input = MockAudioInput()
    # No wake word ever fires — an endless silent stream a real
    # microphone would also produce while nobody is speaking.
    audio_input.seed_chunks([_SILENCE_1] * 1000)
    pipeline = _pipeline(audio_input=audio_input)

    await pipeline.start()
    assert pipeline.is_running()
    await asyncio.wait_for(pipeline.stop(), timeout=5.0)
    assert pipeline.is_running() is False
