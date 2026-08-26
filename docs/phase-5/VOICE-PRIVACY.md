# Voice Privacy

## 1. No raw audio retention by default (brief §50-51)

Neither `voice.core.models.VoiceSession` (in-memory) nor
`app/models/voice.py`'s `VoiceSessionRow` (persisted) has any field
capable of holding raw audio bytes — there is structurally nowhere for a
captured clip to end up, even by accident. Verified directly:
`tests/security/test_phase5_voice_security.py::test_3_no_raw_audio_retention_by_default`
inspects both schemas' field names. No "debug mode" audio-retention toggle
is implemented in this phase (would need a real `AudioInput` to retain
anything from in the first place — see `AUDIO-PIPELINE.md` §3-4).

## 2. Transcript storage and redaction (brief §52)

Transcripts reuse the existing `Conversation`/`Message` tables
(`app/models/conversation.py`) — `VoiceConversationManager.start_session`
creates a real `Conversation` per voice session (unless the caller
supplies an existing one), and every turn writes a `Message` row for both
the user's utterance and VEYRA's spoken response
(`app/services/voice/manager.py::_log_turn`). Before either is written,
`redact_secrets` (`voice/core/privacy.py`) strips password/PIN values,
OTP/verification codes, credit-card-shaped digit runs, and common API-key
prefixes (`sk-`, `ghp_`, `gho_`, `glpat-`, `xox*-`, `Bearer `) — pattern-
based, deliberately biased toward over-redacting a plausible secret rather
than under-redacting a real one. Redaction never applies to text actually
*spoken back* to the user (only to what's persisted), which would
otherwise be confusing.

## 3. Every voice session, every transcript, is user-inspectable

`GET /conversations/{id}/messages` (Phase 1, unchanged) is the real
"transcript" surface — no new, voice-only, harder-to-find endpoint exists
for it (CLAUDE.md: "All memory must be user-inspectable, editable, and
deletable via the API"). `GET /voice/sessions/{id}` returns the session's
own metadata, including its `conversation_id`.

## 4. Cloud boundary

See `CLOUD-BOUNDARY.md` — no audio or transcript leaves the process
without an explicit, checked cloud path; none exists in this phase at all
(no real cloud STT/TTS provider ships — `STT.md` §4, `TTS.md` §3).

## 5. Verified

`tests/unit/test_voice_privacy.py` (6 cases); integration
`test_transcript_is_logged_with_secrets_redacted`
(`tests/integration/test_voice_conversation.py`); security
`test_4_secrets_are_never_logged_verbatim_in_the_transcript`
(`tests/security/test_phase5_voice_security.py`).
