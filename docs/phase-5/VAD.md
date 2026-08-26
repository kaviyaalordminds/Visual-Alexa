# Voice Activity Detection

## 1. Interface

`VoiceActivityDetector.is_speech(audio_chunk: bytes) -> bool`
(`voice/providers/base.py`) — the simplest `Protocol` in this phase, by
design: any temporal smoothing (debounce, hangover time) is the
implementation's own job, never the caller's.

## 2. Shipped implementations

- `NotConfiguredVAD` — always reports silence. Real, ships in this phase,
  never fabricates a speech detection it cannot actually make.
- `MockVAD` (`voice/testing/mocks.py`) — speech/silence decided by a
  seeded set of chunk values, not by inspecting audio content, so tests
  are fully deterministic regardless of what "audio" actually looks like.

## 3. Why no real VAD model ships

Same reason as `WAKE-WORD.md` §2 / `AUDIO-PIPELINE.md` §3-4: no audio
hardware or audio library exists in this environment to validate a real
VAD implementation (energy-based, WebRTC VAD, or model-based) against.

## 4. Role in the pipeline

VAD sits between `AudioInput` and `WakeWordDetector`/`SpeechRecognitionProvider`
— its job is purely to decide *when* to run the (comparatively expensive)
wake-word/STT stage at all, not to interpret content. Nothing downstream
of VAD depends on it existing; `VoiceConversationManager.submit_utterance`
takes an already-recognized transcript string as its input and has no VAD
dependency of its own — see `CONVERSATION.md` §2.
