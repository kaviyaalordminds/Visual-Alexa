# Speech-to-Text

## 1. Interface

```python
class SpeechRecognitionProvider(Protocol):
    def transcribe(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]: ...
    async def detect_language(self, text: str) -> Language: ...
```

`TranscriptChunk` (`voice/core/models.py`) carries `text`, `is_final`,
`confidence`, `language`, `timestamp` — a caller can act on partial
results (brief §15) without waiting for `is_final`.

## 2. LOCAL / CLOUD / AUTO (brief §17-19)

`STTMode` (`voice/core/enums.py`): `LOCAL`, `CLOUD`, `AUTO`. Seeded default
is `stt.mode = "LOCAL"`, `stt.provider = None`
(`app/db/seed_defaults.py`) — no cloud STT is ever silently enabled.
Deciding whether a `CLOUD` call is actually permitted (provider configured,
`cloud_fallback.enabled`, real connectivity via `ConnectivityManager`, and
the user's own privacy settings) is the caller's responsibility, never a
provider's own — no `Protocol` implementation in this phase has network
access at all. See `CLOUD-BOUNDARY.md`.

## 3. Shipped implementations

- `NotConfiguredSTT` — yields no transcripts, `detect_language` always
  returns `Language.UNKNOWN`. Never raises.
- `MockSTT` (`voice/testing/mocks.py`) — yields a scripted sequence of
  `TranscriptChunk`s regardless of the audio stream's actual bytes, while
  still fully consuming the stream (so a caller's own
  backpressure/cancellation behavior is exercised realistically).

## 4. Why no real STT model ships

No audio hardware or library exists in this environment
(`AUDIO-PIPELINE.md` §4); a local model (Whisper-class) or cloud provider
adapter is future work behind this same `Protocol` — genuinely
provider-independent by construction, so adding one later touches no
caller.

## 5. What `VoiceConversationManager` actually receives

`submit_utterance(db, session_id, raw_text, *, stt_confidence)` takes
already-transcribed text plus a confidence score directly — it has no STT
dependency of its own (`CONVERSATION.md` §2). This is what makes the whole
conversation/confirmation/task-execution loop genuinely testable today:
every integration test hands it a string exactly as a real
`SpeechRecognitionProvider`'s final `TranscriptChunk.text` would.

## 6. Mishear clarification (brief acceptance test #8)

`stt_confidence` isn't only a confirmation-authorization gate
(`VOICE-SECURITY.md` §2) — `suggest_correction`
(`voice/core/mishear.py`) uses it to decide whether an unrecognized
"`<verb> <target>`" utterance is worth double-checking at all. Below the
confidence threshold, the target is fuzzy-matched (`difflib
.SequenceMatcher`, stdlib only) against real, currently-registered names
(application names/aliases, via `app/services/application_registry`); a
close-but-not-exact match produces "Did you say Chrome?" instead of
either guessing or failing outright, and the corrected command only runs
after the user confirms. At or above the threshold, the words are trusted
as heard — an unrecognized target still reaches real planning and fails
honestly (`CAPABILITY_UNAVAILABLE`/`APPLICATION_NOT_FOUND`) rather than
being second-guessed. See `voice.core.models.VoiceSession.pending_correction`
and `VoiceConversationManager`'s handling of it
(`services/local-api/app/services/voice/manager.py`).

A real bug this surfaced during its own integration testing: the
`ApplicationRegistry` singleton `app.services.application_registry
.application_registry` is *rebound* (not mutated) each time it's reloaded
(`load_application_registry`'s `global application_registry = ...`) — a
`from app.services.application_registry import application_registry` done
once at another module's import time keeps pointing at the original,
empty registry forever. Fixed by importing the module itself
(`from app.services import application_registry as
application_registry_module`) and reading `.application_registry` fresh
on every call.

## 7. Verified

`tests/unit/test_voice_mishear.py` (10 cases); integration:
`tests/integration/test_voice_conversation.py
::test_mishear_clarification_then_yes_runs_the_corrected_command`,
`::test_mishear_clarification_declined_runs_nothing`, and
`::test_high_confidence_mishear_target_is_trusted_as_heard`, all against
a real registered test application.
