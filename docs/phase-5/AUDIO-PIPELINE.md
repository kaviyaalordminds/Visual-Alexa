# Audio Pipeline

## 1. The chain

MICROPHONE → `AudioInput` → `VoiceActivityDetector` → `WakeWordDetector` →
`SpeechRecognitionProvider` → `LanguageDetector` → `VoiceConversationManager`
→ (Phase 4 `AgentOrchestrator`) → `ResponseGenerator` →
`SpeechSynthesisProvider` → `AudioOutput` → SPEAKER.

Every stage left of `VoiceConversationManager` is provider-independent
(`voice/providers/base.py`'s `Protocol`s) — no vendor SDK is imported
outside a future provider adapter module (CLAUDE.md: "No vendor-specific
AI SDK may be imported outside its designated provider adapter module").

## 2. Interfaces

```python
class AudioInput(Protocol):
    async def start(self, device_id: str | None = None) -> None: ...
    async def stop(self) -> None: ...
    def stream(self) -> AsyncIterator[bytes]: ...
    async def list_devices(self) -> list[AudioDeviceInfo]: ...
```

`AudioOutput`, `VoiceActivityDetector`, `WakeWordDetector`,
`SpeechRecognitionProvider`, `SpeechSynthesisProvider` follow the same
shape (see the module docstring in `voice/providers/base.py` for the full
set). None of them raise when hardware/a model isn't available — every
method returns an honest "nothing" (empty stream, `detected=False`,
`Language.UNKNOWN`) instead.

## 3. What ships in Phase 5

Exactly one real implementation per `Protocol`: `NotConfigured*`. It never
touches hardware, never raises, and never fabricates a detection —
`NotConfiguredAudioInput.stream()` yields nothing, `NotConfiguredVAD
.is_speech()` always returns `False`, `NotConfiguredWakeWord
.process_chunk()` never activates. This mirrors
`vision.core.vision_provider.NotConfiguredVisionProvider` and
`NotConfiguredLLMProvider` exactly (`docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md`
§3). A real `sounddevice`-backed (or platform) provider is future work
behind the same interface — `services/voice/pyproject.toml`'s optional
`audio` extra is where its dependency would be declared, lazily, so
`veyra-voice` itself never requires `sounddevice` just to import.

## 4. Why no real provider was attempted

This container has no `/dev/snd` and no `sounddevice` installed (which
itself needs the system PortAudio library). There is no microphone or
speaker to test against even in principle — a harder constraint than
Phase 2's "Windows-only" (no OS to try at all) or Phase 3's "no vision
model" (there was at least a real Xvfb display for screen capture).
Writing an untested "real" backend here would be indistinguishable from
fabricating verification, which CLAUDE.md's Testing rules forbid.

## 5. What's tested instead

`voice/testing/mocks.py`'s six `Mock*` providers (brief §97/§115) —
deterministic, seedable, no hardware — exercise every caller that depends
on "a provider is configured": `tests/unit/test_voice_providers.py` covers
both the `NotConfigured*` honesty guarantees and the `Mock*` deterministic
behavior (seeded chunks, scripted transcripts, barge-in-safe playback
stopping mid-stream).

## 6. Thread-safety / shutdown (brief §80-84)

Every `Protocol` method is `async` — the whole pipeline is a single-event-
loop, non-blocking design, no separate audio thread to synchronize with.
`AudioInput.stop()`/`AudioOutput.stop()` are the two required cleanup
calls; `VoiceConversationManager.end_session` calls `request_cancellation`
for any active task and persists the session as ended, so a real caller's
shutdown path has one place to release everything.
