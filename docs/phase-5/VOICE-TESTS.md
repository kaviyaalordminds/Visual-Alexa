# Voice Testing Architecture

## 1. Mock-based, CI-compatible by construction (brief §97/§115-116)

No test in this suite requires real microphone/speaker/GPU/cloud-API/
Windows hardware. Six deterministic `Mock*` providers
(`voice/testing/mocks.py`) — `MockAudioInput`, `MockAudioOutput`,
`MockSTT`, `MockTTS`, `MockVAD`, `MockWakeWord` — stand in for every
`Protocol` in `voice/providers/base.py`, seeded with scripted chunks/
transcripts/activations rather than inspecting real audio content.

## 2. Unit tests — pure logic (111 tests, `tests/unit/test_voice_*.py`)

| File | Count | Covers |
|---|---|---|
| `test_voice_state_machine.py` | 9 | Legal/illegal transitions, ERROR's only exit, non-mutating `can_transition` |
| `test_voice_language.py` | 7 | Brief's own EN/Tanglish worked examples + native Tamil script + empty input |
| `test_voice_normalizer.py` | 11 | Filler removal, stutter collapse, wake-word mishear fix, wake-phrase stripping, Tanglish verb+pannu/panni reordering, no invented content |
| `test_voice_interruption.py` | 11 | All 4 interruption types, all 6+ named phrases, "Stop talking" vs. "Stop Chrome" |
| `test_voice_confirmation.py` | 14 | AFFIRM/DENY/UNCLEAR, low-confidence-never-authorizes, hedged phrasing, embedded-denial leniency (and its asymmetry), continue/resume phrases |
| `test_voice_response.py` | 11 | Never-say-Done-on-FAILED, CAPABILITY_UNAVAILABLE honesty, real question passthrough |
| `test_voice_connectivity.py` | 5 | Online/offline/no-checker/raising-checker |
| `test_voice_followup.py` | 8 | Ordinal/number/pronoun resolution, no-fabrication when unresolvable |
| `test_voice_pronunciation.py` | 6 | Known-term rewriting, unrelated text untouched |
| `test_voice_privacy.py` | 6 | Password/OTP/credit-card/API-key redaction, ordinary text untouched |
| `test_voice_providers.py` | 13 | Every `NotConfigured*` honesty guarantee + every `Mock*` deterministic behavior |
| `test_voice_mishear.py` | 10 | Verb/target extraction, fuzzy matching, confidence gating, never fabricating a candidate outside the known list |

## 3. Integration tests — the real pipeline (21 tests)

`tests/integration/test_voice_conversation.py` (15), `test_voice_api.py`
(3), and `test_voice_events.py` (3) drive `VoiceConversationManager`/the
HTTP `/voice` router against the *actual* `AgentOrchestrator`, Policy
Engine, and a real filesystem sandbox — completion, `CAPABILITY_UNAVAILABLE`
honesty, ambiguity + "the second one" follow-up, low-confidence
confirmation never authorizing, confirmation denial, a live-correction
sentence denying a pending confirmation, barge-in, session end, transcript
logging with redaction, the wake-phrase-prefixed "Hey Veyra, open Chrome"
acceptance example, the Tanglish "Downloads folder la latest PDF open
pannu." acceptance example reaching real planning, mishear clarification
(accepted/declined/high-confidence-trusted), a task genuinely paused
externally being resumed on "continue," and every wired `voice.*` event
actually publishing with a redacted payload. No mocking of the Task Engine
itself — the same "real end-to-end" discipline
`tests/integration/test_agent_tasks_api.py` established in Phase 4.

## 4. Security tests — 12 named scenarios (12 tests)

`tests/security/test_phase5_voice_security.py` — see `VOICE-SECURITY.md`
§5 for the full list. Each asserts a denial/honesty path, per CLAUDE.md's
testing rule, not merely a happy path.

## 5. Multilingual corpus

The brief's own EN/Tanglish worked examples double as the multilingual
test corpus (`test_voice_language.py`, `test_voice_response.py`'s
Tanglish-phrasing case) — no larger corpus was assembled, consistent with
"do not claim language accuracy without actual testing" (`LANGUAGE-DETECTION.md`
§2-3).

## 6. Adversarial voice tests

Background noise / false-wake resistance is covered at the provider level
(`MockWakeWord` only activates on one seeded chunk — any other chunk,
including ones a test seeds to represent noise, is a non-activation:
`test_voice_providers.py::test_mock_wake_word_activates_only_on_seeded_chunk`).
Accent/speed/whisper/multi-speaker adversarial testing requires real audio
and a real STT provider, neither of which exists in this environment
(`AUDIO-PIPELINE.md` §4) — not attempted, recorded here rather than
fabricated.

## 7. Real task pausing tests (5 tests, in Phase 1/4's own files)

`tests/unit/test_task_transitions.py::test_executing_can_pause_and_resume`
and `::test_paused_only_resumes_or_cancels_never_skips_to_terminal` cover
the additive `TaskState.PAUSED` transition table.
`tests/integration/test_agent_tasks_api.py
::test_pause_before_run_then_resume_executes_the_full_plan`,
`::test_resume_without_a_pause_is_rejected`, and
`::test_pause_on_a_terminal_task_is_a_harmless_noop` cover the HTTP
`/tasks/{id}/pause`/`/resume` endpoints against the real orchestrator —
added to Phase 4's own test files rather than duplicated into a Phase 5
file, since `TaskState` is a Phase 1/4 contract Phase 5 extended, not a
Phase 5-only concept (`BARGE-IN.md` §5).

## 8. Total

144 tests in the voice-specific files (111 unit + 21 integration + 12
security) plus 5 more for the additive `TaskState.PAUSED` work (§7) — 149
Phase 5 tests total, all passing; see `PHASE-5-TEST-RESULTS.md` for the
current full-monorepo count.
