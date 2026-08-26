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
