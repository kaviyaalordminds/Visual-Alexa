# Voice Subsystem Status

**Updated**: real, local, offline hardware providers now exist — see
`docs/voice-hardware/SETUP.md` for how to install and configure them.
This document is kept for history (what earlier activation sessions
found real vs. missing); the "not real yet" section below no longer
describes the current state of the codebase.

## What's real today

- `services/voice/voice/`'s conversation logic: the state machine, text
  normalization, mishear-correction, interruption/barge-in handling, and
  language detection (English/Tamil/Tanglish), all operating on
  already-transcribed text. `VoiceConversationManager`
  (`app/services/voice/manager.py`) drives real task confirmation/resume
  flows from that text — unchanged by the hardware work below.
- **Wake-word detection**: `OpenWakeWordDetector`
  (`services/voice/voice/providers/real.py`) — real, local, offline
  detection via openWakeWord's pretrained ONNX models. Live-verified.
- **Speech-to-text**: `WhisperSTTProvider` — real, local, offline
  transcription via whisper.cpp (`pywhispercpp` bindings). Live-verified
  end to end via a real Piper→Whisper round trip during development.
- **Text-to-speech**: `PiperTTSProvider` — real, local, offline
  synthesis via Piper. Live-verified.
- **The hardware pipeline**: `VoiceHardwarePipeline`
  (`app/services/voice/pipeline.py`) — the real glue tying
  AudioInput→WakeWordDetector→VoiceActivityDetector→
  SpeechRecognitionProvider→`VoiceConversationManager`→
  SpeechSynthesisProvider→AudioOutput together, with a bounded (never
  unbounded) per-utterance recording loop. This is the first real caller
  of `ActivationSource.WAKE_WORD` and `VoiceState.WAKE_DETECTED`, both of
  which existed in the contracts since Phase 5 but were never reachable.
- `compute_voice_status()` (`app/services/subsystem_health.py`) now
  reports real per-component load results (recorded once at process
  startup by `build_and_start_voice_pipeline`), not a hard-coded
  NOT CONFIGURED.

## What's still not real

- **Microphone/speaker I/O** (`SounddeviceAudioInput`/
  `SounddeviceAudioOutput`) is written and reviewed but could not be
  exercised against real hardware in this repo's own dev/CI sandbox (no
  audio hardware, no PortAudio system library present there) — needs
  verification on a real machine with a microphone (see
  `docs/voice-hardware/SETUP.md`).
- **A custom "Hey VEYRA" wake word** — openWakeWord ships several
  pretrained phrases ("hey_jarvis", "alexa", "hey_mycroft",
  "hey_rhasspy"); a VEYRA-specific phrase needs training data and
  openWakeWord's own training notebook, not shipped here.
- **True streaming STT** — `WhisperSTTProvider.transcribe` is an honest
  batch-mode implementation of the streaming `Protocol` (buffers the
  whole utterance, then transcribes once) — whisper.cpp's own API is not
  incremental, so no implementation here claims otherwise.
- **AI-driven vision** (scene understanding) remains separate and
  unaffected by this work — see `docs/subsystem-activation/VISION-
  STATUS.md`.

## Testing voice today

- `tests/unit/test_real_voice_providers.py` — real, non-mock tests for
  wake-word detection and the energy-based VAD (no external model
  download needed); model-dependent STT/TTS tests skip honestly without
  a real local model file, gated by `VEYRA_TEST_WHISPER_MODEL`/
  `VEYRA_TEST_PIPER_VOICE` env vars.
- `tests/integration/test_voice_hardware_pipeline.py` — the pipeline's
  wiring logic, exercised against `voice.testing.mocks`' deterministic
  fakes (no real audio/model needed to prove the control flow itself).
- `system.voice_health_check` and `GET /system`'s `voice` field/
  `details.voice` reason report the real, current state — which
  component(s) loaded, which didn't, and why.
