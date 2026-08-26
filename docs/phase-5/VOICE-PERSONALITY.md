# Voice Personality

## 1. Concise, natural, never robotic (brief §32-36)

`ResponseGenerator` (`voice/core/response.py`) produces short, direct
sentences reflecting the *actual* `TaskState` — "Done. Chrome is done.",
"I couldn't do that. File not found.", "Okay, cancelled." — never a long
explanation, never a templated apology beyond what's true. No personality
layer sits on top of this to "soften" or elaborate the wording; the
templates themselves are written in plain, spoken register.

## 2. Never claims what didn't happen

The one hard constraint (brief §74-79, §131): `generate_response` reads
only `outcome.state`/`outcome.error` — it cannot say "Done" for a `FAILED`
task, and `CAPABILITY_UNAVAILABLE` always produces "I can't do that — I
don't have that capability yet.", never a fabricated success. Verified
directly: `tests/unit/test_voice_response.py::test_failed_never_says_done`,
`::test_capability_unavailable_is_spoken_honestly_not_as_success`.

## 3. Female voice — a configuration slot, not a shipped voice

See `TTS.md` §4 — `tts.voice`/`tts.provider` settings exist for a future
real provider to bind a specific (female) voice ID to; no commercial voice
is hard-coded or shipped in Phase 5 (brief's own "not hard-coded to a
commercial provider" constraint).

## 4. Multilingual personality

The same plain, direct register carries into `TA`/`TA_EN` phrasings
(`TANGLISH.md` §2) — e.g. `"Sorry, mudiyala."` rather than an elaborate
Tamil paraphrase. Consistency of tone across languages was a design goal;
native-speaker review of whether the Tamil/Tanglish phrasing actually
*reads* as natural was not performed in this environment (`TANGLISH.md`
§3).

## 5. Out of scope for Phase 5

No avatar, no facial expression, no lip-sync — brief §132 explicitly
forbids building these this phase. `VoiceUIState`-shaped events
(`VOICE-EVENTS.md` §3) are prepared so a future avatar can drive its
expressions off real conversation state, without any visual rendering
existing yet.
