# Voice Testing Architecture

## 1. Mock-based, CI-compatible by construction (brief §97/§115-116)

No test in this suite requires real microphone/speaker/GPU/cloud-API/
Windows hardware. Six deterministic `Mock*` providers
(`voice/testing/mocks.py`) — `MockAudioInput`, `MockAudioOutput`,
`MockSTT`, `MockTTS`, `MockVAD`, `MockWakeWord` — stand in for every
`Protocol` in `voice/providers/base.py`, seeded with scripted chunks/
transcripts/activations rather than inspecting real audio content.

## 2. Unit tests — pure logic (97 tests, `tests/unit/test_voice_*.py`)

| File | Count | Covers |
|---|---|---|
| `test_voice_state_machine.py` | 9 | Legal/illegal transitions, ERROR's only exit, non-mutating `can_transition` |
| `test_voice_language.py` | 7 | Brief's own EN/Tanglish worked examples + native Tamil script + empty input |
| `test_voice_normalizer.py` | 11 | Filler removal, stutter collapse, wake-word mishear fix, wake-phrase stripping, Tanglish verb+pannu/panni reordering, no invented content |
| `test_voice_interruption.py` | 11 | All 4 interruption types, all 6+ named phrases, "Stop talking" vs. "Stop Chrome" |
| `test_voice_confirmation.py` | 10 | AFFIRM/DENY/UNCLEAR, low-confidence-never-authorizes, hedged phrasing |
| `test_voice_response.py` | 11 | Never-say-Done-on-FAILED, CAPABILITY_UNAVAILABLE honesty, real question passthrough |
| `test_voice_connectivity.py` | 5 | Online/offline/no-checker/raising-checker |
| `test_voice_followup.py` | 8 | Ordinal/number/pronoun resolution, no-fabrication when unresolvable |
| `test_voice_pronunciation.py` | 6 | Known-term rewriting, unrelated text untouched |
| `test_voice_privacy.py` | 6 | Password/OTP/credit-card/API-key redaction, ordinary text untouched |
| `test_voice_providers.py` | 13 | Every `NotConfigured*` honesty guarantee + every `Mock*` deterministic behavior |

## 3. Integration tests — the real pipeline (13 tests)

`tests/integration/test_voice_conversation.py` (10) and
`test_voice_api.py` (3) drive `VoiceConversationManager`/the HTTP `/voice`
router against the *actual* `AgentOrchestrator`, Policy Engine, and a real
filesystem sandbox — completion, `CAPABILITY_UNAVAILABLE` honesty,
ambiguity + "the second one" follow-up, low-confidence confirmation never
authorizing, confirmation denial, barge-in, session end, transcript
logging with redaction, the wake-phrase-prefixed "Hey Veyra, open Chrome"
acceptance example, and the Tanglish "Downloads folder la latest PDF open
pannu." acceptance example reaching real planning (not just language
detection). No mocking of the Task Engine itself — this is the same "real
end-to-end" discipline `tests/integration/test_agent_tasks_api.py`
established in Phase 4.

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

## 7. Total

122 Phase 5 tests (97 unit + 13 integration + 12 security), all passing;
400 passing across the full monorepo suite (2 pre-existing Phase 2 skips,
Windows-only, unrelated to this phase). See `PHASE-5-TEST-RESULTS.md`.
