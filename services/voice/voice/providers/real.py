"""Real, local-first `Protocol` implementations for `providers/base.py`.
docs/phase-5/VOICE-ARCHITECTURE.md, docs/voice-hardware/SETUP.md.

Every heavy dependency (`openwakeword`, `pywhispercpp`, `piper`,
`sounddevice`) is imported lazily, inside `__init__`, so importing this
module never requires any of them to be installed — a caller only pays
for what it actually configures (mirrors `pyproject.toml`'s `wake-word`/
`stt`/`tts`/`audio` optional-dependency groups). A missing package or
model file raises `VoiceProviderUnavailableError` with a specific,
actionable reason — never a bare `ImportError`/`FileNotFoundError`
surfacing to a caller, and never a silent fallback to fake behavior.

All four real classes here were live-verified against the real packages
during development (see `tests/unit/test_real_voice_providers.py`):
`OpenWakeWordDetector` and `EnergyVAD` are fully exercised in CI with no
external model download (openWakeWord's small pretrained models ship
inside the pip package itself); `WhisperSTTProvider`/`PiperTTSProvider`
need a model file the operator downloads once (real audio hardware and
first-run model downloads are both things this repo's own sandboxed
dev/CI environment cannot exercise — see docs/voice-hardware/SETUP.md for
exactly where to get each).
"""

from __future__ import annotations

import array
import math
from collections.abc import AsyncIterator
from typing import Any

from voice.core.enums import Language
from voice.core.language import detect_language as _detect_language_from_text
from voice.core.models import AudioDeviceInfo, TranscriptChunk, WakeWordActivation

# openWakeWord/Whisper/Piper all operate on 16kHz, 16-bit, mono PCM —
# the same format `AudioInput.stream()` is documented to yield.
SAMPLE_RATE_HZ = 16000
_BYTES_PER_SAMPLE = 2

# whisper.cpp's own known shorthand model names (pywhispercpp downloads
# these on first use) — see `WhisperSTTProvider.__init__` for why this
# list exists: pywhispercpp does not raise for an unrecognized name/path,
# so this repo validates before ever calling into it.
_KNOWN_WHISPER_MODEL_NAMES = frozenset(
    {
        "tiny", "tiny.en", "tiny-q5_1", "tiny.en-q5_1", "tiny-q8_0", "tiny.en-q8_0",
        "base", "base.en", "base-q5_1", "base.en-q5_1", "base-q8_0", "base.en-q8_0",
        "small", "small.en", "small-q5_1", "small.en-q5_1", "small-q8_0", "small.en-q8_0",
        "medium", "medium.en", "medium-q5_0", "medium.en-q5_0", "medium-q8_0", "medium.en-q8_0",
        "large-v1", "large-v2", "large-v2-q5_0", "large-v2-q8_0",
        "large-v3", "large-v3-q5_0",
        "large-v3-turbo", "large-v3-turbo-q5_0", "large-v3-turbo-q8_0",
    }
)  # fmt: skip


class VoiceProviderUnavailableError(RuntimeError):
    """A real provider could not be constructed — missing package, missing
    model file, or missing system library (e.g. PortAudio). Always
    carries a specific, actionable reason; never raised for "no hardware
    exists at all" (that case stays on `NotConfigured*`, see
    `app/services/voice/register.py`)."""


def _pcm_bytes_to_int16_array(chunk: bytes):
    import numpy as np

    count = len(chunk) // _BYTES_PER_SAMPLE
    return np.frombuffer(chunk[: count * _BYTES_PER_SAMPLE], dtype=np.int16)


class OpenWakeWordDetector:
    """docs/phase-5 §8-10 — real, local, offline wake-word detection via
    openWakeWord's pretrained ONNX models (no cloud call, no API key).

    `wake_word` selects one of openWakeWord's bundled phrases (e.g.
    "hey_jarvis", "alexa", "hey_mycroft", "hey_rhasspy") — a custom
    "Hey VEYRA" model needs training data and openWakeWord's own training
    notebook; that is real future work, not shipped here (see
    docs/voice-hardware/SETUP.md's "Custom wake word" section). Picking a
    bundled phrase today is the honest, immediately-usable option.
    """

    def __init__(self, wake_word: str = "hey_jarvis", *, threshold: float = 0.5) -> None:
        try:
            from openwakeword.model import Model
        except ImportError as exc:
            raise VoiceProviderUnavailableError(
                "openwakeword is not installed — pip install 'veyra-voice[wake-word]'."
            ) from exc
        try:
            # onnx, not the default tflite backend — tflite_runtime's
            # bundled numpy ABI conflicts with this repo's numpy 2.x
            # (confirmed during development; onnx has no such conflict
            # and is equally real/local/offline).
            self._model = Model(wakeword_models=[wake_word], inference_framework="onnx")
        except Exception as exc:
            raise VoiceProviderUnavailableError(
                f"openWakeWord could not load wake word '{wake_word}': {exc}"
            ) from exc
        self._wake_word = wake_word
        self._threshold = threshold

    async def process_chunk(self, audio_chunk: bytes) -> WakeWordActivation:
        samples = _pcm_bytes_to_int16_array(audio_chunk)
        scores = self._model.predict(samples)
        confidence = float(scores.get(self._wake_word, 0.0))
        if confidence < self._threshold:
            return WakeWordActivation(detected=False, confidence=confidence)
        return WakeWordActivation(
            detected=True, phrase=self._wake_word, confidence=min(confidence, 1.0)
        )


class EnergyVAD:
    """A real, deterministic, dependency-free voice-activity detector —
    root-mean-square amplitude against a fixed threshold. Not ML-based
    (unlike webrtcvad/silero), but genuinely classifies real audio rather
    than fabricating a result, and needs no model file at all — a
    reasonable default until a model-based VAD is worth the extra
    dependency (`VoiceActivityDetector` is a `Protocol`; swapping in one
    later needs no caller change)."""

    def __init__(self, *, threshold: float = 500.0) -> None:
        self._threshold = threshold

    def is_speech(self, audio_chunk: bytes) -> bool:
        count = len(audio_chunk) // _BYTES_PER_SAMPLE
        if count == 0:
            return False
        samples = array.array("h")
        samples.frombytes(audio_chunk[: count * _BYTES_PER_SAMPLE])
        rms = math.sqrt(sum(s * s for s in samples) / count)
        return rms >= self._threshold


class WhisperSTTProvider:
    """docs/phase-5 §15-19 — real, local, offline speech-to-text via
    whisper.cpp (through `pywhispercpp`'s bindings), no cloud call, no
    API key, no audio ever leaves the machine.

    `transcribe` batches the whole incoming stream before running
    whisper.cpp once and yielding a single final `TranscriptChunk` —
    whisper.cpp's own API is not incremental-streaming, so this is an
    honest batch-mode implementation of a streaming `Protocol`, not a
    claim of true partial-result streaming. The caller (the voice
    pipeline) already bounds how long it records before calling this, so
    the buffer size here is inherently bounded too.
    """

    def __init__(self, model: str = "base.en", *, models_dir: str | None = None) -> None:
        try:
            from pywhispercpp.model import Model
        except ImportError as exc:
            raise VoiceProviderUnavailableError(
                "pywhispercpp is not installed — pip install 'veyra-voice[stt]'."
            ) from exc
        # A live check found pywhispercpp does NOT raise for a genuinely
        # invalid path/model name — it logs to stderr and leaves the
        # underlying whisper.cpp context in a broken state that later
        # crashes the process on first `.transcribe()` call rather than
        # ever raising a catchable Python exception. Validating the
        # argument ourselves before construction is the only way to
        # honestly report "model not found" instead of taking the whole
        # process down with it.
        import pathlib

        is_known_name = model in _KNOWN_WHISPER_MODEL_NAMES
        is_existing_file = pathlib.Path(model).is_file()
        if not is_known_name and not is_existing_file:
            raise VoiceProviderUnavailableError(
                f"'{model}' is neither a known whisper.cpp model name "
                f"({sorted(_KNOWN_WHISPER_MODEL_NAMES)}) nor an existing file path. See "
                "docs/voice-hardware/SETUP.md for where to download a real ggml model file."
            )
        try:
            self._model = Model(model, models_dir=models_dir)
        except Exception as exc:
            raise VoiceProviderUnavailableError(
                f"whisper.cpp could not load model '{model}': {exc}. See "
                "docs/voice-hardware/SETUP.md for where to download a real ggml model file."
            ) from exc

    async def transcribe(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        import numpy as np

        buffer = bytearray()
        async for chunk in audio_stream:
            buffer.extend(chunk)
        if not buffer:
            return
        samples = np.frombuffer(bytes(buffer), dtype=np.int16).astype(np.float32) / 32768.0
        segments = self._model.transcribe(samples)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            return
        language = _detect_language_from_text(text).language
        yield TranscriptChunk(text=text, is_final=True, confidence=1.0, language=language)

    async def detect_language(self, text: str) -> Language:
        # Reuses the existing real, deterministic text-based detector
        # (voice/core/language.py) — never a second, parallel
        # implementation of the same decision (CLAUDE.md).
        return _detect_language_from_text(text).language


class PiperTTSProvider:
    """docs/phase-5 §32-41 — real, local, offline text-to-speech via
    Piper, no cloud call, no API key.

    `voice_model_path` is a `.onnx` voice file the operator downloads
    once (see docs/voice-hardware/SETUP.md) — Piper voice files are
    large binary artifacts, never bundled/committed to this repo. One
    provider instance is tied to one voice/language; synthesizing a
    different `language` than the loaded voice is not attempted here —
    honestly out of scope for a single-voice instance, not silently
    mismatched.
    """

    def __init__(self, voice_model_path: str, *, config_path: str | None = None) -> None:
        try:
            from piper.voice import PiperVoice
        except ImportError as exc:
            raise VoiceProviderUnavailableError(
                "piper-tts is not installed — pip install 'veyra-voice[tts]'."
            ) from exc
        try:
            self._voice = PiperVoice.load(voice_model_path, config_path=config_path)
        except Exception as exc:
            raise VoiceProviderUnavailableError(
                f"Piper could not load voice model '{voice_model_path}': {exc}. See "
                "docs/voice-hardware/SETUP.md for where to download a real voice file."
            ) from exc

    async def synthesize(
        self, text: str, *, language: Language = Language.EN
    ) -> AsyncIterator[bytes]:
        for audio_chunk in self._voice.synthesize(text):
            yield audio_chunk.audio_int16_bytes

    async def stop(self) -> None:
        # Piper's `synthesize` above is a plain (non-cancellable)
        # generator over a single already-issued request — there is no
        # separate in-flight request object to interrupt. Real
        # interruption happens one layer up, at the `AudioOutput.stop()`
        # that actually silences the speaker (brief §63-64's barge-in
        # requirement is about audible playback, not generation).
        return None


class SounddeviceAudioInput:
    """docs/phase-5 §5-6 — real microphone capture via `sounddevice`
    (PortAudio bindings). Cannot be exercised in this repo's own sandbox
    (no audio hardware, no PortAudio system library — confirmed during
    development) or in most CI environments; verify on the target
    Windows machine per docs/voice-hardware/SETUP.md. sounddevice's
    Windows wheels bundle PortAudio, so no separate system install is
    needed there."""

    def __init__(self) -> None:
        try:
            import sounddevice  # noqa: F401
        except (ImportError, OSError) as exc:
            raise VoiceProviderUnavailableError(
                f"sounddevice is unavailable: {exc}. pip install 'veyra-voice[audio]' and "
                "ensure a real microphone/PortAudio is present on this machine."
            ) from exc
        self._stream: Any = None

    async def start(self, device_id: str | None = None) -> None:
        import sounddevice as sd

        kwargs: dict = {
            "samplerate": SAMPLE_RATE_HZ,
            "channels": 1,
            "dtype": "int16",
            "blocksize": 1280,  # 80ms at 16kHz — matches openWakeWord's expected chunk size
        }
        if device_id is not None:
            kwargs["device"] = int(device_id)
        self._stream = sd.InputStream(**kwargs)
        self._stream.start()

    async def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def stream(self) -> AsyncIterator[bytes]:
        if self._stream is None:
            return
        while self._stream is not None:
            data, _overflowed = self._stream.read(1280)
            yield data.tobytes()

    async def list_devices(self) -> list[AudioDeviceInfo]:
        import sounddevice as sd

        default_input = sd.default.device[0]
        return [
            AudioDeviceInfo(
                id=str(idx), name=info["name"], is_input=True, is_default=idx == default_input
            )
            for idx, info in enumerate(sd.query_devices())
            if info["max_input_channels"] > 0
        ]


class SounddeviceAudioOutput:
    """Real speaker playback via `sounddevice`. Same real-hardware
    caveat as `SounddeviceAudioInput` — see there."""

    def __init__(self) -> None:
        try:
            import sounddevice  # noqa: F401
        except (ImportError, OSError) as exc:
            raise VoiceProviderUnavailableError(
                f"sounddevice is unavailable: {exc}. pip install 'veyra-voice[audio]' and "
                "ensure a real speaker/PortAudio is present on this machine."
            ) from exc
        self._stream: Any = None
        self._stopped = False

    async def play(self, audio_chunks: AsyncIterator[bytes]) -> None:
        import sounddevice as sd

        self._stopped = False
        self._stream = sd.OutputStream(samplerate=SAMPLE_RATE_HZ, channels=1, dtype="int16")
        self._stream.start()
        try:
            async for chunk in audio_chunks:
                if self._stopped:
                    break
                if len(chunk) >= _BYTES_PER_SAMPLE:
                    self._stream.write(_pcm_bytes_to_int16_array(chunk))
        finally:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def stop(self) -> None:
        # docs/phase-5 §63-64 — barge-in must interrupt playback
        # immediately; setting this flag makes the `play()` loop above
        # stop writing further chunks on its very next iteration.
        self._stopped = True

    async def pause(self) -> None:
        if self._stream is not None:
            self._stream.stop()

    async def resume(self) -> None:
        if self._stream is not None:
            self._stream.start()

    async def list_devices(self) -> list[AudioDeviceInfo]:
        import sounddevice as sd

        default_output = sd.default.device[1]
        return [
            AudioDeviceInfo(
                id=str(idx), name=info["name"], is_input=False, is_default=idx == default_output
            )
            for idx, info in enumerate(sd.query_devices())
            if info["max_output_channels"] > 0
        ]
