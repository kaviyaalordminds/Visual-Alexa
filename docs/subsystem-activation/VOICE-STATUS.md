# Voice Subsystem Status

**Current status in this environment: NOT CONFIGURED**
Reason: no STT/TTS/wake-word provider declared, and — more fundamentally
— this build has no real audio implementation wired in regardless of
configuration.

## What's real today

`services/voice/voice/`'s conversation logic is real: the state machine,
text normalization, mishear-correction, interruption/barge-in handling,
and language detection (English/Tamil/Tanglish) all operate on already-
transcribed text. `VoiceConversationManager`
(`app/services/voice/manager.py`) drives real task confirmation/resume
flows from that text.

## What's not real yet

The hardware-facing half — microphone capture, wake-word detection,
speech-to-text, text-to-speech, speaker playback
(`services/voice/voice/providers/base.py`'s `AudioInput`/`AudioOutput`/
`WakeWordDetector`/`SpeechRecognitionProvider`/`SpeechSynthesisProvider`
Protocols) — ships only `NotConfigured*` implementations. No real audio
SDK (e.g. `sounddevice`, a cloud STT/TTS client) is wired in, and this
activation did not add one — that would be a new, unjustified dependency
for a capability with no real hardware to exercise in this environment,
and a substantial scope expansion beyond "activate the existing
architecture."

## Configuration surface (added this activation)

```
VEYRA_STT_PROVIDER=
VEYRA_TTS_PROVIDER=
VEYRA_WAKE_WORD_PROVIDER=
```

Declaring one of these does not make voice CONNECTED — it only makes the
health check's reason more specific ("configured for provider 'X', but no
real implementation is wired in this build") instead of a bare
"nothing configured." This is deliberate honesty, not a bug: `/system`
must never claim CONNECTED for a capability that cannot actually run.

## How to make voice real in a future phase

Implement a concrete provider class per Protocol in a new
`voice/providers/real.py`-style module (matching `providers/base.py`'s own
docstring, which already anticipates this exact extension point), wire it
into `VoiceConversationManager`, and update `compute_voice_status()`
(`app/services/subsystem_health.py`) to check whether a real (not
`NotConfigured*`) provider is actually constructed before reporting
anything other than NOT CONFIGURED.

## Testing voice today

`system.voice_health_check` (`POST
/tools/system.voice_health_check/invoke`) reports exactly this state —
configured intent (if any) plus an honest "no real implementation" reason.
There is no "Test Voice" microphone/speaker round-trip possible in this
build, because there is no real audio pipeline to test.
