# Tanglish (Code-Mixed English/Tamil)

## 1. Where it's handled

Two separate stages, deliberately: `LanguageDetector` (`LANGUAGE-DETECTION.md`)
decides *that* an utterance is Tanglish; `SpeechNormalizer`
(`voice/core/normalizer.py`) cleans up *what was said* without touching
its language — normalization (filler removal, stutter collapse, known
mishear correction) is language-agnostic and runs the same way regardless
of `TA_EN` vs. `EN`. Neither stage translates Tamil to English or attempts
to interpret intent — that's still `IntentInterpreter`'s job alone (brief
§27), unchanged for any language.

## 2. Response generation

`ResponseGenerator` (`voice/core/response.py`) carries a parallel `TA_EN`
phrasing for every outcome template (`_completed_text`, `_failed_text`,
`_cancelled_text`, `_timed_out_text`, `ask_yes_no_text`, `goodbye_text`,
...) — e.g. `"Done pannitten. {subject} ready."` instead of `"Done.
{subject} is done."`. These are direct, non-native-reviewed translations
of the same English templates — a genuine best effort, not a
verified-natural Tamil voice (see §3).

## 3. Explicit limitation: translation quality is unverified

No native Tamil speaker reviewed the `TA`/`TA_EN` response phrasings in
this environment. They are real, they render, and
`tests/unit/test_voice_response.py::test_tanglish_language_produces_tanglish_phrasing`
confirms the language selector actually changes the output — but
naturalness/correctness of the Tamil/Tanglish text itself is not
independently verified, consistent with the brief's own "do not claim
accuracy without actual testing."

## 4. A real bug this phase's own testing found

Submitting the brief's own examples through the real
`VoiceConversationManager` (not just `detect_language` in isolation)
surfaced two genuine gaps in getting from a Tanglish/wake-word-prefixed
utterance to something `IntentInterpreter` actually understands:

1. **A leading wake phrase blocked intent understanding entirely.**
   `IntentInterpreter.interpret("Hey Veyra, open Chrome")` returned
   `MISSING_INFORMATION`, while `interpret("open Chrome")` alone returned
   `UNDERSTOOD` — the "Hey Veyra," prefix (a HEARING-layer artifact) was
   never stripped before being handed to Phase 4's intent parser. Fixed by
   adding `_WAKE_PHRASE_RE` to `normalize_command`
   (`voice/core/normalizer.py`) — strips a leading `"(hey )?veyra,"`
   case-insensitively, nowhere else in the sentence.
2. **`"<object> <verb> pannu/panni"` word order wasn't understood either** —
   `"Chrome open pannu."` also returned `MISSING_INFORMATION`, since
   `IntentInterpreter`'s templates expect English verb-first phrasing
   (`"open Chrome"`). Fixed by adding `_TANGLISH_VERB_PANNU_RE`, a single-
   clause reorder (`"Chrome open pannu."` → `"open Chrome"`) for a small,
   named verb set (open/close/search/play/send/delete/create/find).

Both are real fixes, covered by regression tests
(`tests/unit/test_voice_normalizer.py::test_strips_leading_wake_phrase`,
`::test_reorders_tanglish_object_verb_pannu_to_verb_object`) and by
integration tests proving the *rewritten* text reaches real planning
(`tests/integration/test_voice_conversation.py
::test_wake_phrase_prefix_does_not_block_intent_understanding`,
`::test_tanglish_folder_example_reaches_real_planning`). Documented here
per the project's disclosure discipline (`docs/phase-4/PHASE-4-TEST-RESULTS.md`
§3's precedent).

The reorder is deliberately narrow: a negative lookahead refuses to match
a sentence with more than one `pannu`/`panni` clause (e.g. the brief's own
three-clause example, `"Chrome open panni YouTube la AR Rahman song search
pannu."`), leaving it completely untouched rather than risk producing
garbled text — see `test_does_not_reorder_a_multi_clause_tanglish_sentence`.
That specific multi-action sentence remains a documented, honest gap: no
attempt is made to decompose it into multiple tasks or a single coherent
one.

## 5. Worked example end-to-end

`"Downloads folder la latest PDF open pannu."` →
`detect_language` returns `TA_EN` → `normalize_command` reorders it to
`"open Downloads folder la latest PDF"` (§4.2) → `IntentInterpreter`
returns `UNDERSTOOD` → `TaskPlanner` runs the real `filesystem.search`
tool against the real filesystem → whatever `TaskState` results is spoken
back using the `TA_EN` template set. Verified for real end-to-end:
`tests/integration/test_voice_conversation.py
::test_tanglish_folder_example_reaches_real_planning`. No separate
Tanglish intent-parsing path exists — the rewritten text is *still* parsed
by the real `IntentInterpreter`, the same principle `CONVERSATION.md`
describes for English follow-ups.
