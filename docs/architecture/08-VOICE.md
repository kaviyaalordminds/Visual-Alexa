# 08 — Voice Architecture

## 1. Components (future; interfaces defined now)

```
WakeWordEngine          # local, always-on-capable only when explicitly
                        # enabled by the user; OFF by default
STTEngine                 # pluggable: local or cloud, behind one interface
LanguageDetector             # distinct pipeline stage — decoupled from STT
                        # engine choice (see rationale below)
IntentProcessor                # turns recognized text + language context
                        # into a structured request for the planner
ConversationManager               # multi-turn state, independent of
                        # which STT/TTS/model backend is active
TTSService                          # pluggable: local or cloud
VoiceStateManager                     # drives avatar/UI voice state
                        # (LISTENING/THINKING/SPEAKING — see 02)
```

## 2. Why LanguageDetector is a separate stage

`docs/research/04-TECHNICAL-LIMITATIONS.md` and
`docs/research/08-UNSOLVED-PROBLEMS.md` both flag Tanglish (code-mixed
Tamil-English) conversational accuracy as a genuinely unverified,
industry-wide open problem. Coupling language handling to one specific STT
vendor's language parameter would make it impossible to iterate on
Tamil/Tanglish quality independently of STT vendor choice, or to route
different languages to different STT backends. Making `LanguageDetector` its
own pipeline stage — consuming raw or partially-transcribed audio/text and
producing a language/code-mix signal used to select STT/TTS backend and
prompt behavior — keeps this an empirical, swappable decision rather than a
one-time architectural commitment.

## 3. Local vs. cloud, without rewriting the conversation system

`STTEngine` and `TTSService` are interfaces; `ConversationManager` and
`IntentProcessor` depend only on those interfaces, never on a specific
vendor. This mirrors the `AIProvider` pattern in `03-AI-ARCHITECTURE.md` —
the same LOCAL/HYBRID/CLOUD mode concept applies to voice independently of
the reasoning model's mode (e.g., local STT + cloud reasoning is a valid
HYBRID configuration).

## 4. Supported languages (target)

English, Tamil, Tanglish (code-mixed) — declared as a target in
`ConversationManager`'s language configuration; Phase 1 ships the
configuration surface (`Voice: NOT CONFIGURED` as the default system state)
with no actual STT/TTS integration.

## 5. Privacy default

Microphone access is OFF unless explicitly enabled by the user
(product brief §29); `WakeWordEngine` must never be active without that
explicit enablement, and its state must be visible in the status UI.

## 6. Phase 1 scope

Delivered: interfaces, mode configuration, and the "NOT CONFIGURED" default
system state. Not delivered: any real audio capture, STT, TTS, or wake-word
detection — explicitly out of Phase 1 scope per the brief §39.

## 7. Phase 5: the real voice pipeline, hardware still unverified

`docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md` and
`docs/phase-5/VOICE-ARCHITECTURE.md` deliver every interface this section
sketched, for real: `SpeechRecognitionProvider`/`SpeechSynthesisProvider`
(`docs/phase-5/STT.md`, `TTS.md`) are the actual `STTEngine`/`TTSService`
interfaces this section described; `LanguageDetector`
(`docs/phase-5/LANGUAGE-DETECTION.md`) is real, pure-heuristic code,
tested against the brief's own EN/Tanglish examples — exactly the
"empirical, swappable decision" §2 called for; `VoiceConversationManager`
(`docs/phase-5/CONVERSATION.md`) is the real `ConversationManager`,
binding to Phase 4's `AgentOrchestrator` rather than reimplementing intent
classification. `VoiceStateManager` is `VoiceStateMachine`
(`docs/phase-5/VOICE-STATE-MACHINE.md`); its `voice.ui_state.changed`
event (`docs/phase-5/VOICE-EVENTS.md` §3) is reserved for the future
avatar's LISTENING/THINKING/SPEAKING drive this section anticipated, not
yet consumed by anything.

Only `WakeWordEngine`/`STTEngine`/`TTSService`'s *real* backends remain
unbuilt — every `Protocol` ships exactly one honest `NotConfigured*`
implementation plus deterministic `Mock*` providers for testing
(`docs/phase-5/AUDIO-PIPELINE.md` §3), the same precedent Phase 3/4 set
for `VisionProvider`/`LLMProvider`. This container has no audio hardware
or audio library at all — a harder gap than Phase 2's Windows-only limit
— so no real backend was attempted here; see
`docs/phase-5/PHASE-5-TEST-RESULTS.md`.
