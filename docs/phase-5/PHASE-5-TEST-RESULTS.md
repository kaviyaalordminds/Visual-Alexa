# Phase 5 Test Results

Run in this environment (Linux container, no audio hardware, real
SQLite, real filesystem sandbox, real HTTP via `httpx.AsyncClient`),
2026-08-26.

## 1. Summary

- **Full repository suite**: 400 passed, 0 failed, 2 skipped (pre-existing
  Phase 2 Windows-only skips, unrelated to this phase).
- **New Phase 5 tests**: 122 (97 unit, 13 integration, 12 security), all
  new files, all passing.
- **Lint**: `ruff check` clean across all five Python packages and `tests/`.
- **Types**: `mypy` clean — `veyra_contracts` (11 files), `computer_control`
  (25), `vision` (19), `veyra-voice` (18), `app` (77).

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
| `voice.*` event publishing | **Declared, not wired** — `EventType.VOICE_*` values exist; no caller publishes them yet (`VOICE-EVENTS.md` §2) |
| Voice hotkey / push-to-talk OS binding | **Reviewed only** — enum/`ActivationSource.HOTKEY` real and tested; no OS-level hotkey capture exists to test |

## 3. Real bugs found and fixed during this phase's own verification

Genuine end-to-end testing against the real `IntentInterpreter` (not just
unit tests against fakes) surfaced three real defects, all fixed and
covered by regression tests — the same disclosure discipline
`docs/phase-4/PHASE-4-TEST-RESULTS.md` §3 established:

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

All three were caught specifically *because* this phase's verification
insisted on running the brief's own worked examples through the real
`AgentOrchestrator`/`IntentInterpreter`, not merely testing
`detect_language`/`classify_interruption` in isolation.

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
| 8 | STT mishear "Open Rome" → "Did you say Chrome?" | **Not implemented — documented gap** — `SpeechNormalizer` only fixes known mishears of VEYRA's own name, not general application-name mishears; `IntentInterpreter` (Phase 4) has no "did you mean" suggestion mechanism for an unrecognized application either. Would need work in both packages, out of scope for this phase's own modules |
| 9 | Two files named similarly, disambiguation | **Passes** — real `WAITING_USER` + real `AmbiguityCandidate`s + "the second one" follow-up resolves to a concrete file, re-verified by the real `IntentInterpreter` |
| 10 | Live correction ("Actually, don't open it") mid-speech | **Partially passes — documented gap** — any speech during `RESPONDING` is a real barge-in (stops speech immediately); but if it arrives while a confirmation prompt is specifically pending, `parse_confirmation` only matches a small set of *exact* denial phrases, not a denial embedded in a longer sentence like "Actually, don't open it" — that utterance currently classifies `UNCLEAR` and re-prompts ("Please say yes or no.") rather than being understood as "no." Documented here rather than overclaimed |

## 5. Known limitations

- **No real audio I/O, wake-word, VAD, STT, or TTS model** — every
  provider ships only `NotConfigured*` (honest, non-raising) and `Mock*`
  (deterministic, CI-only) implementations. No audio hardware or library
  exists in this environment to validate a real backend against.
- **`voice.*` events are declared but not published** — see §2 and
  `VOICE-EVENTS.md` §2.
- **Tanglish reordering is narrow** — only single-clause `"<object> <verb>
  pannu/panni"` sentences are rewritten; a multi-clause sentence (the
  brief's own third Tanglish example) is left untouched rather than risk
  garbling it (`TANGLISH.md` §4).
- **No STT-mishear-based clarification** ("Did you say Chrome?") — brief
  acceptance test #8, not implemented this phase (§4).
- **`parse_confirmation` is exact-phrase, not free-text** — a denial
  phrased as a full sentence rather than a short "no"/"cancel" isn't
  recognized as `DENY` (§4, acceptance test #10).
- **Tamil/Tanglish response phrasing is not native-speaker reviewed**
  (`TANGLISH.md` §3).
- **No P50/P95 latency data for anything audio-related** — see
  `PERFORMANCE.md` §2.
- **Voice hotkey/push-to-talk has no real OS binding** — enum and
  activation-source plumbing exist and are tested; no hotkey capture
  library is wired in.

## 6. Technical debt

- `app/services/voice/manager.py`'s `PAUSE_TASK` interruption only pauses
  VEYRA's speech, never the underlying task — Phase 4's `AgentOrchestrator`
  has no real pause/resume mechanism to bind it to (`BARGE-IN.md` §3).
  Documented directly in the code, not silently under-delivered.
- No caching layer for TTS output — moot without a real TTS provider to
  cache from (`TTS.md` §6).
- `VoiceSession.last_candidates`/`last_task_goal` are in-memory only, per
  process — a restart loses in-flight follow-up context (acceptable: this
  is explicitly short-term context, never long-term memory, per brief
  §28-31).
