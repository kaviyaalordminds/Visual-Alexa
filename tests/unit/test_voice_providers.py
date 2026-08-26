"""docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §3 — every NotConfigured*
provider must be honest (report unavailable, never raise, never fabricate
a detection) and every Mock* provider must behave deterministically for
CI (brief §97/§115), with no audio hardware anywhere in either."""

from __future__ import annotations

from voice.core.enums import Language
from voice.core.models import WakeWordActivation
from voice.providers.base import (
    NotConfiguredAudioInput,
    NotConfiguredAudioOutput,
    NotConfiguredSTT,
    NotConfiguredTTS,
    NotConfiguredVAD,
    NotConfiguredWakeWord,
)
from voice.testing import MockAudioInput, MockAudioOutput, MockSTT, MockTTS, MockVAD, MockWakeWord


async def test_not_configured_audio_input_never_raises_and_yields_nothing():
    provider = NotConfiguredAudioInput()
    await provider.start()
    chunks = [chunk async for chunk in provider.stream()]
    assert chunks == []
    assert await provider.list_devices() == []
    await provider.stop()


async def test_not_configured_audio_output_is_a_safe_noop():
    provider = NotConfiguredAudioOutput()

    async def _chunks():
        yield b"data"

    await provider.play(_chunks())
    await provider.stop()
    await provider.pause()
    await provider.resume()
    assert await provider.list_devices() == []


def test_not_configured_vad_never_fabricates_speech():
    assert NotConfiguredVAD().is_speech(b"anything") is False


async def test_not_configured_wake_word_never_false_activates():
    result = await NotConfiguredWakeWord().process_chunk(b"anything")
    assert result == WakeWordActivation(detected=False)


async def test_not_configured_stt_yields_nothing():
    async def _chunks():
        yield b"data"

    transcripts = [t async for t in NotConfiguredSTT().transcribe(_chunks())]
    assert transcripts == []
    assert await NotConfiguredSTT().detect_language("hello") == Language.UNKNOWN


async def test_not_configured_tts_yields_no_audio():
    audio = [chunk async for chunk in NotConfiguredTTS().synthesize("hello")]
    assert audio == []


async def test_mock_audio_input_streams_seeded_chunks():
    provider = MockAudioInput()
    provider.seed_chunks([b"a", b"b"])
    await provider.start()
    assert provider.started is True
    chunks = [chunk async for chunk in provider.stream()]
    assert chunks == [b"a", b"b"]


async def test_mock_audio_output_records_playback():
    provider = MockAudioOutput()

    async def _chunks():
        yield b"one"
        yield b"two"

    await provider.play(_chunks())
    assert provider.played == [b"one", b"two"]


async def test_mock_audio_output_stop_during_playback_halts_it():
    """Simulates barge-in: stop() called partway through an in-progress
    play() must be observed by that same call, not just future ones."""
    provider = MockAudioOutput()

    async def _chunks():
        yield b"one"
        await provider.stop()
        yield b"two"
        yield b"three"

    await provider.play(_chunks())
    assert provider.played == [b"one"]


def test_mock_vad_reports_speech_only_for_seeded_chunks():
    vad = MockVAD()
    vad.seed_speech(b"speech-chunk")
    assert vad.is_speech(b"speech-chunk") is True
    assert vad.is_speech(b"silence-chunk") is False


async def test_mock_wake_word_activates_only_on_seeded_chunk():
    detector = MockWakeWord(wake_chunk=b"WAKE")
    activation = await detector.process_chunk(b"WAKE")
    assert activation.detected is True
    non_activation = await detector.process_chunk(b"noise")
    assert non_activation.detected is False


async def test_mock_stt_yields_seeded_transcripts_regardless_of_audio():
    stt = MockSTT()

    async def _chunks():
        yield b"anything"

    transcripts = [t async for t in stt.transcribe(_chunks())]
    assert len(transcripts) == 1
    assert transcripts[0].text == "open chrome"


async def test_mock_tts_records_synthesized_text():
    tts = MockTTS()
    audio = [chunk async for chunk in tts.synthesize("hello there")]
    assert audio == [b"mock-audio-chunk"]
    assert tts.synthesized_text == ["hello there"]
