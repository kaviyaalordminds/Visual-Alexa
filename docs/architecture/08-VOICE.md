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
