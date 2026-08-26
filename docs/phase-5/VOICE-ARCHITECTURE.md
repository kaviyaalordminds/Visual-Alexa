# Voice Architecture

## 1. HEARING + SPEAKING, not a third brain

Brief §130: VOICE = HEARING + SPEAKING, PHASE 4 = THINKING, PHASE 3 =
SEEING, PHASE 2 = ACTING. Concretely: a `SpeechRecognitionProvider` turns
audio into text; `VoiceConversationManager` turns that text into a real
`Task.description` and runs it through the *exact*, unmodified
`AgentOrchestrator` Phase 4 already built; `ResponseGenerator` turns the
resulting `TaskState` into text; a `SpeechSynthesisProvider` turns that
text into audio. No step in this chain calls `IntentInterpreter` a second
time, and none of it can execute a tool directly — see `CONVERSATION.md`.

## 2. Package layout

- `services/voice/voice/core/` — pure Python, no I/O, no OS dependency:
  enums, pydantic models, `state_machine.py`, `language.py`,
  `normalizer.py`, `interruption.py`, `confirmation.py`, `response.py`,
  `connectivity.py`, `followup.py`, `pronunciation.py`, `privacy.py`.
  Fully real, fully unit-tested (`tests/unit/test_voice_*.py`).
- `services/voice/voice/providers/base.py` — the `AudioInput`/
  `AudioOutput`/`VoiceActivityDetector`/`WakeWordDetector`/
  `SpeechRecognitionProvider`/`SpeechSynthesisProvider` `Protocol`s, plus
  the one honest `NotConfigured*` implementation each ships (see
  `AUDIO-PIPELINE.md` §3).
- `services/voice/voice/testing/mocks.py` — deterministic `Mock*`
  providers for CI (brief §97/§115) — no hardware, no network, no model.
- `services/local-api/app/services/voice/manager.py` —
  `VoiceConversationManager`, the only place the voice package and the
  Task Engine meet. Needs DB access, so it lives in `local-api`, exactly
  as Phase 3's tool registration lived in `local-api` while perception
  logic lived in `vision` (`docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md` §4).
- `services/local-api/app/api/voice.py` — thin HTTP wrapper:
  `POST /voice/sessions`, `POST /voice/sessions/{id}/utterances`,
  `POST /voice/sessions/{id}/finish_response`,
  `POST /voice/sessions/{id}/end`, `GET /voice/sessions/{id}`.

## 3. Why `services/voice` is a separate package

Same reasoning as Phase 2/3, not Phase 4: audio/speech capability code
doesn't need direct database access, so it doesn't belong inside
`local-api`. It depends only on `veyra-contracts` — not on
`computer_control` or `vision` (voice needs neither OS control nor screen
perception) and not on `local-api` itself.

## 4. State machine

`VoiceState` (`voice/core/enums.py`) unifies the brief's separately
described "session status" (§12) and "state machine" (§43) into one field,
`VoiceSession.status` — see `VOICE-STATE-MACHINE.md`.

## 5. What's real vs. reviewed-only here

Every module under `voice/core/` and the `local-api` binding layer above
it is real, runs, and is tested end-to-end against the actual
`AgentOrchestrator` (`tests/integration/test_voice_conversation.py`,
`tests/integration/test_voice_api.py`). No real audio I/O, wake-word, VAD,
STT, or TTS model exists anywhere in this environment (no `/dev/snd`, no
`sounddevice`) — the provider `Protocol`s and their `NotConfigured*`/
`Mock*` implementations are real and tested, but nothing behind them
touches actual hardware. See `AUDIO-PIPELINE.md` §3-4 for exactly where
that line sits.
