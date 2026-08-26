# Phase 5 Implementation Plan — Advanced Voice Intelligence Engine

Written before substantial implementation, per the Phase 5 brief §0.
Records what Phase 1-4 actually built (re-verified, not assumed), where
this phase's suggested design reuses vs. adapts it, and the technology
decisions with rationale — same discipline as the prior three phase
plans.

## 1. What Phase 1-4 actually implemented (repository inspection findings)

- **Voice was never built, only sketched.** `docs/architecture/08-VOICE.md`
  (Phase 1) defines `WakeWordEngine`/`STTEngine`/`LanguageDetector`/
  `IntentProcessor`/`ConversationManager`/`TTSService`/`VoiceStateManager`
  as names in a diagram — grepping `services/` for any of them, or for
  `sounddevice`/`pyaudio`/`whisper`/`vosk`, returns nothing. Two
  `SystemSetting` keys already exist and are seeded OFF
  (`microphone.enabled`, `voice.configured` — `app/db/seed_defaults.py`),
  confirming Phase 1's own "NOT CONFIGURED" default and nothing more.
- **No audio hardware or audio library exists in this environment.**
  `/dev/snd` does not exist; `sounddevice` (which itself requires the
  system PortAudio library) is not installed. This is a harder
  constraint than Phase 2's "Windows-only" or Phase 3's "no vision model"
  gaps: there is no real microphone or speaker to test against *even in
  principle* on this host, the same way there was at least a real (if
  virtual) X display for Phase 2/3's screen capture. Every audio I/O
  path in this phase is therefore in the same bucket as Phase 2's
  Windows-only backends — real, reviewed code, structurally impossible
  to runtime-verify here — **except** the pieces that are pure text/logic
  (language detection, normalization, state machine, conversation
  context, response generation), which are fully real and fully tested,
  mirroring Phase 3's OCR-vs-UI-Automation split exactly.
- **`Conversation`/`Message` tables already exist** (Phase 1,
  `app/models/conversation.py`) and `Task.conversation_id` already links
  a task to one. **Phase 5 reuses this directly** for turn history rather
  than inventing a parallel transcript store — each voice turn's
  transcript is stored as a `Message` (`role="user"`), exactly as a typed
  turn would be.
- **`AgentOrchestrator`/`IntentInterpreter`/`TaskPlanner` are real and
  working** (Phase 4). Per brief §27 ("do not duplicate intent
  interpretation... voice layer handles speech, Phase 4 handles intent"),
  **the voice layer never reimplements intent classification.** A voice
  turn becomes an ordinary `Task` (`description` = the normalized
  transcript) run through the exact same `AgentOrchestrator.run`/
  `execute_tool_call` path a typed command already uses — see §5.
- **The Task Engine's cancellation mechanism already exists and is
  reusable as-is** (`app/services/agent/orchestrator.request_cancellation`).
  Barge-in's "cancel the active task" half (brief §13) calls this
  directly rather than building a second cancellation signal.
- **`EventType`/`event_bus`** (Phase 1, extended in Phase 4) already
  supports exactly the publish/subscribe shape brief §44's `voice.*`
  events need. Extended additively, not replaced.
- **`ErrorCategory`** (Phase 1, extended in Phase 2/4) already covers
  several of brief §111's voice error names under existing names
  (`NETWORK_ERROR`, `PERMISSION_DENIED`, `TIMEOUT`); genuinely new voice-
  specific categories are added additively — see §6.

## 2. The central technical decision: what's genuinely testable here

Sharper than Phase 2/3's split, because there is no real device or model
of any kind available, only pure logic:

| Capability | Verified here? |
|---|---|
| `LanguageDetector` (EN / TA / TA_EN heuristics) | **Yes — real, tested against the brief's own example sentences** |
| `SpeechNormalizer` (filler/repeat removal, Tanglish transliteration, typo correction) | **Yes — real, pure Python** |
| `VoiceStateMachine` | **Yes — real, mirrors `TaskStateMachine`'s pattern exactly** |
| `InterruptionClassifier` (STOP_SPEAKING vs. CANCEL_TASK vs. PAUSE_TASK vs. END_SESSION) | **Yes — real, pure Python** |
| `VoiceConfirmationParser` (yes/no/unclear) | **Yes — real, pure Python** |
| `ResponseGenerator` (task outcome → natural EN/TA/TA_EN text) | **Yes — real, pure Python** |
| `ConnectivityManager` | **Yes — real, against an injected checker function** |
| Follow-up/pronoun resolution against session context | **Yes — real, pure Python** |
| Full conversation loop: transcript → Task → Phase 4 → response | **Yes — real, against the actual `AgentOrchestrator`, exactly like Phase 4's own integration tests** |
| `AudioInput`/`AudioOutput`/`AudioDeviceManager` | Interfaces + `Mock*` providers real and tested; a real `sounddevice`-backed provider is written, lazy-imported, but **not runtime-verified** — no audio hardware exists in this container at all |
| `WakeWordDetector`, `VoiceActivityDetector` | Interfaces + `Mock*` providers real and tested; no real local wake-word/VAD model ships in this phase (see §3) |
| `SpeechRecognitionProvider`, `SpeechSynthesisProvider` | Interfaces + `Mock*` providers real and tested; no real STT/TTS model ships in this phase (see §3) |

This is, if anything, a *cleaner* split than Phase 2/3: the brief itself
mandates CI-compatible mock providers (§97, §115, §116) as first-class
architecture, not merely a testing convenience — so the "abstraction +
mock" pieces are exactly what a correct Phase 5 is supposed to ship, not
a concession to this environment's limits.

## 3. No real STT/TTS/wake-word model ships in Phase 5

Same precedent as Phase 3's `NotConfiguredVisionProvider` and Phase 4's
`NotConfiguredLLMProvider`: every provider `Protocol` in this phase ships
exactly one non-mock implementation, `NotConfigured*Provider`, which
reports unavailable rather than raising or fabricating output. Wiring a
real local model (e.g., a Whisper-class STT, a Piper-class TTS, a
Porcupine-class wake-word engine) is future work behind the same
interface — brief §16-17/§35/§114 ask for the abstraction and provider-
independence, not a shipped model, and §17/§113 explicitly plan for
"local STT... configurable" as forward-looking. The `Mock*` providers
(brief's own §97/§115) are what make the rest of the pipeline (state
machine, conversation manager, response generation, Phase 4 integration)
genuinely testable today without waiting for a real model.

## 4. Package placement: new `services/voice` (`veyra-voice`)

Mirrors Phase 3's `services/vision` decision, not Phase 4's "no new
package" one — audio I/O and speech processing are the same kind of
capability code Phase 2 (`computer_control`) and Phase 3 (`vision`) put in
their own installable packages: conceptually reusable, provider-swappable,
and requiring no database access of their own. `services/voice/voice/`
holds every pure/testable piece from §2's table plus the provider
`Protocol`s and `Mock*` implementations. It depends only on
`veyra-contracts` — not on `computer_control` or `vision` (voice doesn't
need OS control or screen perception directly) and not on `local-api`.

The binding to Phase 4 — creating a real `Task`, running the real
`AgentOrchestrator`, holding the live `VoiceSession` registry — needs
database access and therefore lives in `services/local-api/app/services/voice/`,
exactly mirroring how Phase 3's tool registration lived in `local-api`
while the perception logic lived in `vision`.

## 5. Voice → Task Engine binding: no duplicate intent path

A voice turn's normalized transcript becomes `Task.description` and runs
through the *exact* `AgentOrchestrator.run` an existing `POST /tasks` +
`POST /tasks/{id}/run` call already uses — same `IntentInterpreter`, same
`TaskPlanner`, same Policy Engine, same audit trail. `VoiceConversationManager`
(`app/services/voice/conversation.py`) does not call `IntentInterpreter`
directly; it only decides *what text* to hand to the orchestrator (after
normalization and follow-up/pronoun rewriting — see §7) and *how to speak*
whatever `TaskState` the orchestrator reaches. Barge-in cancellation
(brief §13) calls the exact same `request_cancellation(task_id)` Phase 4
already exposes.

## 6. Additive contract extensions

- `veyra_contracts.enums.ErrorCategory` gains the voice-specific values
  from brief §111 that don't already exist under another name:
  `MIC_NOT_FOUND`, `MIC_PERMISSION_DENIED`, `AUDIO_INPUT_FAILED`,
  `AUDIO_OUTPUT_FAILED`, `WAKE_WORD_ERROR`, `VAD_ERROR`, `STT_ERROR`,
  `STT_TIMEOUT`, `LANGUAGE_UNKNOWN`, `LOW_CONFIDENCE`, `TTS_ERROR`,
  `TTS_TIMEOUT`, `CLOUD_PROVIDER_ERROR`, `VOICE_CANCELLED`,
  `SESSION_TIMEOUT`. (`NETWORK_ERROR`/`PERMISSION_DENIED`/`TIMEOUT`
  already existed and are reused for the brief's `NETWORK_UNAVAILABLE`/
  the generic timeout/permission cases.)
- `veyra_contracts.enums.EventType` gains the `voice.*` events from brief
  §44, additively, following the exact `task.*` precedent Phase 4 set.
- Voice-specific enums with no cross-phase meaning (`VoiceSessionStatus`,
  `VoiceState`, `Language`, `InterruptionType`, `ConnectivityState`,
  `WakeWordMode`) live in `services/voice/voice/core/enums.py`, not
  `veyra_contracts` — same reasoning as Phase 3 keeping `PrivacyLevel` in
  `vision.core.privacy` rather than the shared contracts package: nothing
  outside the voice pipeline needs these shapes yet.

## 7. Follow-up / pronoun resolution without duplicating intent logic

Phase 4's `open_file` planner already returns ambiguity candidates
(`AmbiguityCandidate(id=path, label=name)`) when multiple files match.
`VoiceSession` keeps the *last* such candidate list in memory. When the
next utterance is an ordinal/pronoun follow-up ("the second one", "open
it", "the first result"), `resolve_followup` (pure function,
`services/voice/voice/core/followup.py`) rewrites it into a concrete new
utterance naming the resolved candidate's label (e.g. `"open
project2.txt"`) — still parsed by the real `IntentInterpreter` afterward,
never a bypass. If no candidates are in context, or the reference doesn't
resolve, the rewrite is a no-op and the original (now probably
`MISSING_INFORMATION`) text proceeds normally, which correctly surfaces
as a clarifying question rather than a guess.

## 8. Database: one new table, settings reuse existing pattern

- **`voice_sessions`** (new, minimal) — `id`, `user_id`, `started_at`,
  `last_activity_at`, `language`, `status`, `active_task_id`,
  `activation_source`, `audio_device`, `ended_at`. No raw audio, no
  transcript column (see next point) — matches brief §51's "no raw audio
  retention by default."
- **No `voice_events` table** — `EventType.VOICE_*` events already have a
  home in the existing `event_bus`; a second persisted copy would
  duplicate `AuditLog`+`event_bus`'s existing job, the same reasoning
  Phase 4 applied to rejecting a `task_events` table.
- **No `voice_preferences` table** — `SystemSetting` (Phase 1's existing
  generic key/value store) already holds exactly this shape; brief
  §105's full settings list (`voice.enabled`, `wake_word.*`, `stt.*`,
  `tts.*`, `cloud_fallback.enabled`, `audio.*`) is added to
  `DEFAULT_SETTINGS`, all conservative-by-default (`False`/`None`),
  seeded via one new migration — the same pattern Phase 2/3 already used
  twice.
- **Transcripts** reuse the existing `Message` table
  (`conversation_id` → `Task.conversation_id`), not a new column —
  brief §52's transcript-privacy rules (redact sensitive values, avoid
  unnecessary persistence) apply to it via the same redaction vocabulary
  Phase 1's audit log and Phase 3's `PrivacyRedactor` already established
  (see `VOICE-PRIVACY.md`).

## 9. Tool registration: none

Voice produces `Task`s; it does not itself register any new Tool Registry
entries. There is nothing here shaped like a tool call — `ConversationManager`
calls `AgentOrchestrator` methods directly, in-process, exactly as
`app/api/tasks.py`'s endpoints already do.

## 10. Documentation set for this phase

`docs/phase-5/{VOICE-ARCHITECTURE,AUDIO-PIPELINE,WAKE-WORD,VAD,STT,
LANGUAGE-DETECTION,TANGLISH,CONVERSATION,BARGE-IN,TTS,VOICE-PERSONALITY,
VOICE-PRIVACY,CLOUD-BOUNDARY,OFFLINE-MODE,VOICE-SECURITY,
VOICE-STATE-MACHINE,VOICE-EVENTS,PERFORMANCE,VOICE-TESTS,
PHASE-5-TEST-RESULTS}.md`, each stating plainly what was verified for
real in this environment (language detection, normalization, state
machine, conversation logic, response generation, Phase 4 integration —
most of the phase) versus what is real-but-unverifiable-here code (any
actual audio I/O, wake-word, VAD, STT, TTS) versus what is deliberately
not shipped at all (a real model behind any provider interface).
