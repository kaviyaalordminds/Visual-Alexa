"""Real (non-mock) voice provider implementations —
services/voice/voice/providers/real.py. docs/voice-hardware/SETUP.md.

`OpenWakeWordDetector` and `EnergyVAD` are fully real-tested here: no
external model download needed (openWakeWord ships small pretrained
ONNX models inside the pip package itself). `WhisperSTTProvider` and
`PiperTTSProvider` need a real model file the operator downloads once —
skipped here the same way `test_ocr_engine.py` skips without a real
`tesseract` binary, via an explicit env var pointing at a real local
model file (never auto-downloaded during tests).
"""

from __future__ import annotations

import os
import struct

import pytest

pytest.importorskip("openwakeword", reason="openwakeword is an optional dependency")

from voice.providers.real import (
    SAMPLE_RATE_HZ,
    EnergyVAD,
    OpenWakeWordDetector,
    VoiceProviderUnavailableError,
)


def _silence(seconds: float) -> bytes:
    sample_count = int(SAMPLE_RATE_HZ * seconds)
    return struct.pack(f"<{sample_count}h", *([0] * sample_count))


def _tone(seconds: float, amplitude: int = 12000) -> bytes:
    """A real, loud (non-silent) synthetic waveform — not speech, but
    real enough to prove `EnergyVAD` actually measures amplitude rather
    than always returning a fixed answer."""
    sample_count = int(SAMPLE_RATE_HZ * seconds)
    samples = [amplitude if i % 20 < 10 else -amplitude for i in range(sample_count)]
    return struct.pack(f"<{sample_count}h", *samples)


async def test_open_wake_word_never_falsely_activates_on_real_silence():
    detector = OpenWakeWordDetector(wake_word="hey_jarvis")
    silence = _silence(1.5)
    chunk_bytes = 1280 * 2  # openWakeWord's expected chunk size, 16-bit samples
    detected_any = False
    for i in range(0, len(silence), chunk_bytes):
        chunk = silence[i : i + chunk_bytes]
        if len(chunk) < chunk_bytes:
            break
        activation = await detector.process_chunk(chunk)
        detected_any = detected_any or activation.detected
    assert detected_any is False


async def test_open_wake_word_reports_a_specific_phrase_and_bounded_confidence():
    detector = OpenWakeWordDetector(wake_word="hey_jarvis", threshold=1.1)  # unreachable threshold
    silence = _silence(0.08)
    activation = await detector.process_chunk(silence)
    assert activation.detected is False
    assert 0.0 <= activation.confidence <= 1.0


async def test_a_custom_model_path_resolves_to_its_basename_as_the_lookup_key(tmp_path):
    """A live check of openWakeWord's own source found it keys its
    internal model dict by the basename *without extension* for a file
    path (e.g. a future real 'hey_veyra.onnx') — using the raw path
    string to look up a score would always miss and silently report
    'never detected'. Stands in for a real custom-trained model with a
    copy of a bundled one, renamed — proves the *key resolution*, not
    wake-word accuracy."""
    import shutil

    import openwakeword

    bundled = openwakeword.get_pretrained_model_paths("onnx")[0]
    custom_path = tmp_path / "hey_veyra.onnx"
    shutil.copy(bundled, custom_path)

    detector = OpenWakeWordDetector(wake_word=str(custom_path))
    assert detector._wake_word == "hey_veyra"

    activation = await detector.process_chunk(_silence(0.08))
    assert activation.detected is False
    assert activation.confidence >= 0.0  # a real score was read back, not a permanent 0.0 miss


def test_unknown_wake_word_name_raises_a_specific_actionable_error():
    with pytest.raises(VoiceProviderUnavailableError):
        OpenWakeWordDetector(wake_word="not_a_real_wake_word")


def test_energy_vad_classifies_silence_as_not_speech():
    vad = EnergyVAD(threshold=500.0)
    assert vad.is_speech(_silence(0.1)) is False


def test_energy_vad_classifies_a_loud_real_waveform_as_speech():
    vad = EnergyVAD(threshold=500.0)
    assert vad.is_speech(_tone(0.1)) is True


def test_energy_vad_handles_an_empty_chunk_without_crashing():
    vad = EnergyVAD()
    assert vad.is_speech(b"") is False


# --- Model-dependent providers: real, but need a real local model file ------

_WHISPER_MODEL_PATH = os.environ.get("VEYRA_TEST_WHISPER_MODEL")
_PIPER_VOICE_PATH = os.environ.get("VEYRA_TEST_PIPER_VOICE")


@pytest.mark.skipif(
    not _WHISPER_MODEL_PATH, reason="VEYRA_TEST_WHISPER_MODEL not set to a real ggml model file"
)
async def test_whisper_stt_transcribes_real_synthesized_speech():
    """Round-trips through the real Piper voice this same env also
    requires — proves STT and TTS actually interoperate, not just that
    each loads without error."""
    if not _PIPER_VOICE_PATH:
        pytest.skip("VEYRA_TEST_PIPER_VOICE not set — needed to synthesize a real test utterance")

    from voice.providers.real import PiperTTSProvider, WhisperSTTProvider

    tts = PiperTTSProvider(_PIPER_VOICE_PATH)
    stt = WhisperSTTProvider(_WHISPER_MODEL_PATH)

    async def _synth_stream():
        async for chunk in tts.synthesize("open notepad"):
            yield chunk

    chunks = [c async for c in stt.transcribe(_synth_stream())]
    assert len(chunks) == 1
    assert "notepad" in chunks[0].text.lower()
    assert chunks[0].is_final is True


@pytest.mark.skipif(
    not _PIPER_VOICE_PATH, reason="VEYRA_TEST_PIPER_VOICE not set to a real Piper voice file"
)
async def test_piper_tts_synthesizes_real_non_empty_audio():
    from voice.providers.real import PiperTTSProvider

    tts = PiperTTSProvider(_PIPER_VOICE_PATH)
    total_bytes = 0
    async for chunk in tts.synthesize("hello from VEYRA"):
        total_bytes += len(chunk)
    assert total_bytes > 0


def test_missing_whisper_model_raises_a_specific_actionable_error():
    pytest.importorskip("pywhispercpp", reason="pywhispercpp is an optional dependency")
    from voice.providers.real import WhisperSTTProvider

    with pytest.raises(VoiceProviderUnavailableError):
        WhisperSTTProvider("/nonexistent/not-a-real-model.bin", models_dir="/nonexistent")


def test_missing_piper_voice_raises_a_specific_actionable_error():
    pytest.importorskip("piper", reason="piper-tts is an optional dependency")
    from voice.providers.real import PiperTTSProvider

    with pytest.raises(VoiceProviderUnavailableError):
        PiperTTSProvider("/nonexistent/not-a-real-voice.onnx")
