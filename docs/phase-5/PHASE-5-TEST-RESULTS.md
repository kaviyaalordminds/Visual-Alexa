# Phase 5 Test Results

Run in this environment (Linux container, no audio hardware, real
SQLite, real filesystem sandbox, real HTTP via `httpx.AsyncClient`),
2026-08-26 (initial phase) and follow-up gap-closing work the same day.

## 1. Summary

- **Full repository suite**: 428 passed, 0 failed, 2 skipped (pre-existing
  Phase 2 Windows-only skips, unrelated to this phase) — see the repo's
  own CI/`scripts/check-python.sh` output for the exact current count.
  Confirmed stable across multiple repeated full-suite runs, not just one
  green run (§3 explains why that repetition mattered this time).
- **Phase 5 tests**: 144 in the voice-specific files (111 unit, 21
  integration, 12 security) plus 6 more added to Phase 1/4's own
  `test_task_transitions.py`/`test_agent_tasks_api.py` for the additive
  `TaskState.PAUSED` work and the orchestrator bugs in §3 (§7) — 150
  total, all passing.
- **Lint**: `ruff check` clean across all five Python packages and `tests/`.
- **Types**: `mypy` clean — `veyra_contracts` (11 files), `computer_control`
  (25), `vision` (19), `veyra-voice` (19), `app` (77).

## 2. What was verified for real vs. reviewed-only vs. not shipped

| Area | Status |
|---|---|
| `LanguageDetector` (EN/TA/TA_EN, brief's own worked examples) | **Real** — pure Python, tested against the brief's exact sentences |
| `SpeechNormalizer` (fillers, stutters, mishears, wake-phrase strip, Tanglish reorder) | **Real** — pure Python |
| `VoiceStateMachine` | **Real** — mirrors `TaskStateMachine`'s pattern; caught and fixed one real bug (§3) |
| `InterruptionClassifier` | **Real** — pure Python |
| `VoiceConfirmationParser` | **Real** — pure Python, confidence-gated |
| `ResponseGenerator` (EN/TA/TA_EN) | **Real** — pure Python; Tamil/Tanglish phrasing not native-reviewed (`TANGLISH.md` §3) |
| `ConnectivityManager` | **Real** — against an injected checker |
| Follow-up/pronoun resolution | **Real** — against real `AmbiguityCandidate`s from the real planner |
| `redact_secrets` | **Real** — pure Python |
| Full voice→Task→Phase 4→response loop | **Real** — against the actual `AgentOrchestrator`, real filesystem, real SQLite |
| HTTP `/voice/*` API | **Real** — exercised via `httpx.AsyncClient` against the real app |
| `NotConfigured*` providers (Audio/VAD/WakeWord/STT/TTS) | **Real** — honest no-op/unavailable behavior verified |
| `Mock*` providers | **Real** — deterministic, tested |
| Any actual audio capture/wake-word/VAD/STT/TTS | **Not shipped** — no audio hardware or library exists in this environment (`AUDIO-PIPELINE.md` §3-4); a real backend is future work behind the same `Protocol`s |
| `voice.*` event publishing | **Real** — 7 of 9 events genuinely publish through `event_bus` (`VOICE-EVENTS.md` §2); the 3 unwired ones have no real trigger (no wake-word/streaming-STT/avatar) and are deliberately not faked |
| STT-mishear clarification ("Did you say Chrome?") | **Real** — `suggest_correction` fuzzy-matches against real registered names, gated by STT confidence (`STT.md` §6) |
| Free-text confirmation ("Actually, don't open it") | **Real for DENY** — embedded-phrase matching, asymmetric by design (never for AFFIRM) (`VOICE-SECURITY.md` §2) |
| Real task pausing (`TaskState.PAUSED`) | **Real** — orchestrator + HTTP `/tasks/{id}/pause`/`/resume`; not wired into the voice layer's own `PAUSE_TASK` interruption, for a real architectural reason, not an oversight (`BARGE-IN.md` §5) |
| Voice hotkey / push-to-talk OS binding | **Reviewed only** — enum/`ActivationSource.HOTKEY` real and tested; no OS-level hotkey capture exists to test |

## 3. Real bugs found and fixed during this phase's own verification

Genuine end-to-end testing against the real `IntentInterpreter` (not just
unit tests against fakes) surfaced three real defects during the initial
phase, all fixed and covered by regression tests — the same disclosure
discipline `docs/phase-4/PHASE-4-TEST-RESULTS.md` §3 established:

1. **`VoiceState.ERROR`'s only intended legal exit (`RECOVERY`) was not
   actually legal.** The transition table marked `ERROR`'s row as an empty
   frozenset with a `# Terminal.` comment, while the function's own
   top-of-body guard assumed `RECOVERY` was reachable from `ERROR`. Caught
   by `tests/unit/test_voice_state_machine.py::test_errors_only_legal_exit_is_recovery`
   before anything shipped. Fixed — see `VOICE-STATE-MACHINE.md` §4.
2. **A leading wake phrase ("Hey Veyra,") silently blocked intent
   understanding** — `IntentInterpreter.interpret("Hey Veyra, open
   Chrome")` returned `MISSING_INFORMATION` while `"open Chrome"` alone
   returned `UNDERSTOOD`. This would have made the brief's own first
   acceptance example ("Hey Veyra, open Chrome") fail outright. Fixed by
   stripping the wake phrase in `SpeechNormalizer` — see `TANGLISH.md` §4.
3. **Tanglish's own `"<object> <verb> pannu/panni"` word order wasn't
   understood either** — `"Chrome open pannu."` also returned
   `MISSING_INFORMATION`. Fixed with a narrow, single-clause reorder — see
   `TANGLISH.md` §4.

A fourth was caught the same way during the follow-up gap-closing work:

4. **The `ApplicationRegistry` singleton was captured stale at import
   time.** `app.services.application_registry.load_application_registry`
   *rebinds* the module's `application_registry` name (`global
   application_registry = ...`) each time it reloads; a
   `from app.services.application_registry import application_registry`
   done once in `VoiceConversationManager` at process-startup import time
   kept pointing at the original, empty registry forever, so mishear
   suggestions against a real registered application never fired. Caught
   by `tests/integration/test_voice_conversation.py
   ::test_mishear_clarification_then_yes_runs_the_corrected_command`
   immediately failing with the wrong outcome. Fixed by importing the
   module itself (`from app.services import application_registry as
   application_registry_module`) and reading `.application_registry`
   fresh on every call — see `STT.md` §6.

Two more were found the same way, deeper in Phase 4's own
`AgentOrchestrator` (`services/local-api/app/services/agent/orchestrator.py`)
— not Phase 5 code, but surfaced because this phase's gap-closing work
added more background-task-driven integration tests that exercise it
concurrently and more variously than Phase 4's own test suite did:

5. **A real, observable race: `run()` and `_fail_at_planning()` each
   persisted a formality-only `WAITING_PERMISSION` state with its own
   `_save()` (a real DB commit) immediately before superseding it with
   `EXECUTING` or `FAILED`.** `TaskStateMachine.transition()` itself is
   pure in-memory; only `_save()` makes a state observable to a concurrent
   reader. The state machine's legal-transition table requires every plan
   to exit `PLANNING` via `WAITING_PERMISSION` or `WAITING_USER` even when
   the plan never actually needs confirmation (a genuinely SAFE plan, or
   one that's failing outright for `CAPABILITY_UNAVAILABLE`/`UNSAFE`/
   `INVALID`), so this was a real bug, not a test artifact: a concurrent
   `GET /tasks/{id}` could observe a task falsely "waiting for permission"
   when it was never going to ask for any. Root-caused with a standalone
   concurrent-reproduction script (`asyncio.gather` over several
   simultaneous create+run+poll cycles), confirmed fixed the same way
   (24/24 clean across 3 runs) and via 6x-repeated runs of
   `tests/integration/test_agent_tasks_api.py` (previously ~83% flaky on
   `test_delete_files_returns_capability_unavailable_never_deletes` before
   the `_fail_at_planning` half of the fix, 0/6 after). Fixed by merging
   each transition pair into a single `_save()` call — the real
   confirmation-prompt logic lives entirely in a separate, later code path
   inside `_execute_plan` and is unaffected.
6. **`_recover()`'s `REPLAN` branch would always raise
   `IllegalTaskTransitionError` the one time it was ever actually reached
   — not a race, a guaranteed crash.** It transitioned the task through
   `PLANNING` (with its own `_save()`) before calling `_fail()`, but
   `_fail()` itself transitions to `FAILED`, and `PLANNING`'s only legal
   exits are `WAITING_PERMISSION`/`WAITING_USER` — `PLANNING -> FAILED` is
   illegal. `RecoveryManager.decide()` can legitimately choose `REPLAN`
   (a retryable error persisting past `max_recovery_attempts`, with replan
   budget still available — `tests/unit/test_agent_recovery.py` already
   covered that decision in isolation), but nothing had ever exercised the
   orchestrator's own handling of that decision end-to-end, so this went
   uncaught. `RECOVERING -> FAILED` is directly legal, so the fix simply
   fails from `RECOVERING` without the unreachable `PLANNING` detour.
   Caught and regression-tested by
   `tests/integration/test_agent_tasks_api.py::test_replan_decision_fails_cleanly_without_crashing`
   (forces every tool call to fail with a retryable error, with a budget
   that exhausts retries on the first attempt and still has replan budget
   left).

All six were caught specifically *because* this phase's verification
insisted on running the brief's own worked examples — and, for the last
two, concurrent/adversarial execution paths — through the real
`AgentOrchestrator`/`IntentInterpreter`, not merely testing
`detect_language`/`classify_interruption`/`RecoveryManager.decide()` in
isolation.

## 4. Acceptance tests (brief §120-129)

| # | Scenario | Result |
|---|---|---|
| 1 | "Hey Veyra, open Chrome" | **Passes the pipeline, honestly `CAPABILITY_UNAVAILABLE`** — wake phrase stripped, intent `UNDERSTOOD`, planning runs for real; Chrome isn't a registered application in this test environment (same category as Phase 4's own "no Chrome tool" finding), so the honest outcome is `CAPABILITY_UNAVAILABLE`, not a fabricated launch |
| 2 | "Downloads folder la latest PDF open pannu." | **Passes** — Tanglish reorder + real `filesystem.search`, verified end-to-end (`test_tanglish_folder_example_reaches_real_planning`) |
| 3 | "Stop." mid-speech | **Passes** — real barge-in, `stop_speaking=True`, state returns to `LISTENING` |
| 4 | CRITICAL-action voice confirmation ("Delete all files in Downloads") | **Passes via injected fixture** — no real CRITICAL-risk tool exists to trigger this organically (same gap Phase 4 documented for its own confirmation flow), so a `RiskLevel.CRITICAL` plan is injected via `monkeypatch` exactly as `docs/phase-4/CONFIRMATION.md` does; the resulting grant is real, `ALLOW_ONCE`, never `ALWAYS_ALLOW` |
| 5 | "Turn on the AC" | **Passes** — `CAPABILITY_UNAVAILABLE`, no network scan (no IoT tool exists to scan with) |
| 6 | Offline local pipeline continuing ("Open Notepad") | **Passes structurally, not exercised as a dedicated offline test** — no stage in the local voice→Task pipeline makes a network call regardless of connectivity (`OFFLINE-MODE.md` §2); not specifically re-run with a simulated-offline `ConnectivityManager` since nothing in the path consults it |
| 7 | Offline cloud-only-feature honest refusal | **N/A — mechanism exists, nothing to refuse yet** — `ConnectivityManager.cloud_features_available()` is real and tested in isolation; no cloud-only feature exists in this phase to wire the refusal message to (`CLOUD-BOUNDARY.md` §3) |
| 8 | STT mishear "Open Rome" → "Did you say Chrome?" | **Passes** — `suggest_correction` fuzzy-matches the target against real registered application names at low confidence and asks "Did you say X?"; confirming runs the corrected command for real, declining runs nothing (`STT.md` §6) |
| 9 | Two files named similarly, disambiguation | **Passes** — real `WAITING_USER` + real `AmbiguityCandidate`s + "the second one" follow-up resolves to a concrete file, re-verified by the real `IntentInterpreter` |
| 10 | Live correction ("Actually, don't open it") mid-speech | **Passes** — the barge-in stops speech immediately regardless; when it arrives while a confirmation is specifically pending, `parse_confirmation` now recognizes a `DENY` phrase embedded in the sentence (not just an exact match) and treats it as "no" — `tests/integration/test_voice_conversation.py::test_live_correction_sentence_denies_a_pending_confirmation` |

## 5. Known limitations

- **No real audio I/O, wake-word, VAD, STT, or TTS model** — every
  provider ships only `NotConfigured*` (honest, non-raising) and `Mock*`
  (deterministic, CI-only) implementations. No audio hardware or library
  exists in this environment to validate a real backend against.
- **3 of 9 `voice.*` events are still unwired** (`voice.wake_detected`,
  `voice.transcript.partial`, `voice.ui_state.changed`) — no real trigger
  exists yet (no wake-word/streaming-STT/avatar); see `VOICE-EVENTS.md` §2.
- **Tanglish reordering is narrow** — only single-clause `"<object> <verb>
  pannu/panni"` sentences are rewritten; a multi-clause sentence (the
  brief's own third Tanglish example) is left untouched rather than risk
  garbling it (`TANGLISH.md` §4).
- **Mishear clarification only covers a small "`<verb> <target>`" shape**
  (open/close/search/play/send/delete/create/find) and only suggests
  application names/aliases already registered — a mishear of a filename
  or a person's name isn't covered (`STT.md` §6).
- **`parse_confirmation`'s free-text leniency is DENY-only** — an
  affirmation embedded in a longer sentence ("Yeah, sure, go ahead and do
  it") still isn't recognized unless it's an exact phrase; only widened
  for denial, deliberately (`VOICE-SECURITY.md` §2).
- **Tamil/Tanglish response phrasing is not native-speaker reviewed**
  (`TANGLISH.md` §3).
- **No P50/P95 latency data for anything audio-related** — see
  `PERFORMANCE.md` §2.
- **Voice hotkey/push-to-talk has no real OS binding** — enum and
  activation-source plumbing exist and are tested; no hotkey capture
  library is wired in.

## 6. Technical debt

- `app/services/voice/manager.py`'s `PAUSE_TASK` interruption still only
  pauses VEYRA's speech, never the underlying task — not because no real
  pause mechanism exists (it does, see §7), but because a voice turn's
  own execution is synchronous with respect to that turn (`submit_utterance`
  awaits `AgentOrchestrator.run` to completion), so there is no in-flight
  step left to pause by the time the interruption is recognized. Closing
  this fully would need voice turns to run task execution concurrently
  with the ability to receive a new utterance — out of Phase 5's scope.
  Documented directly in the code (`BARGE-IN.md` §5), not silently
  under-delivered.
- No caching layer for TTS output — moot without a real TTS provider to
  cache from (`TTS.md` §6).
- `VoiceSession.last_candidates`/`last_task_goal` are in-memory only, per
  process — a restart loses in-flight follow-up context (acceptable: this
  is explicitly short-term context, never long-term memory, per brief
  §28-31).

## 7. Follow-up gap-closing work (same day)

After the initial Phase 5 delivery, four previously-documented gaps were
closed for real, each verified against the actual `AgentOrchestrator`/
`IntentInterpreter`, not merely unit-tested in isolation:

1. **STT-mishear clarification** (`voice/core/mishear.py`,
   `STT.md` §6) — closes acceptance test #8.
2. **Free-text confirmation for denial** (`voice/core/confirmation.py`,
   `VOICE-SECURITY.md` §2) — closes acceptance test #10.
3. **`voice.*` event publishing** (`app/services/voice/manager.py`,
   `VOICE-EVENTS.md` §2) — 7 of 9 events now genuinely fire.
4. **Real task pausing** (`TaskState.PAUSED`, additive to
   `veyra_contracts` — a Phase 4 contract extended from Phase 5 for a
   genuine, justified reason; `AgentOrchestrator.request_pause`/
   `resume_after_pause`; HTTP `POST /tasks/{id}/pause`/`/resume`;
   `BARGE-IN.md` §5) — real at the orchestrator/HTTP level; the voice
   layer's own `PAUSE_TASK` interruption still can't use it directly, for
   the architectural reason recorded in §6, not because the mechanism is
   fake.

One deliberate decision recorded here: PAUSE_TASK's known limitation was
*not* "fixed" by making the voice layer call `request_pause` regardless
of correctness — doing so would have introduced a real bug (a stale pause
flag wrongly re-pausing a later, unrelated resume of the same task). The
real fix was building the mechanism correctly at the layer where it's
actually safe to use (the Task Engine, for concurrently-executing tasks)
and being honest that the voice layer's current synchronous per-turn
design has no matching integration point yet.
