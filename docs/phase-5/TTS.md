# Text-to-Speech

## 1. Interface

```python
class SpeechSynthesisProvider(Protocol):
    def synthesize(
        self, text: str, *, language: Language = Language.EN
    ) -> AsyncIterator[bytes]: ...
    async def stop(self) -> None: ...
```

Streaming by design (brief §72 — "do not wait for the full response
before speaking"): a caller can start playing audio chunks as they arrive
rather than waiting for the entire utterance to synthesize.

## 2. Shipped implementations

- `NotConfiguredTTS` — synthesizes silence (yields no chunks), `stop()` is
  a no-op. Never raises.
- `MockTTS` (`voice/testing/mocks.py`) — records every `synthesize()`
  call's text in `synthesized_text` and yields seeded audio chunks, so
  tests can assert what VEYRA "said" without any real audio.

## 3. Why no real TTS model ships

Same reason as `STT.md` §4 — no audio hardware/library in this
environment. A local (Piper-class) or cloud provider adapter is future
work behind this same interface.

## 4. Voice profile — not hard-coded to a commercial provider

The brief asks for a female `VoiceProfile` concept, Tamil/mixed-language
support, and configurable speech_rate/pitch/volume. `DEFAULT_SETTINGS`
already models the configurable half: `tts.provider` (`None` by default —
no vendor chosen), `tts.voice`, `tts.speed` (`1.0`), `tts.pitch` (`1.0`)
(`app/db/seed_defaults.py`). A `VoiceProfile` pydantic model binding these
to a specific provider's voice ID is provider-adapter work, not shipped in
this phase — declaring one without a real provider behind it would be
unverifiable configuration, not a tested capability.

## 5. Pronunciation dictionary (brief §37-41)

`PronunciationDictionary`/`apply_pronunciations` (`voice/core/pronunciation.py`)
rewrites known terms into phonetic-friendly spellings *only* for the copy
handed to TTS — `"VEYRA"` → `"Vay-rah"`, `"VS Code"` → `"V S Code"`,
`"GitHub"` → `"Git Hub"`, `"OpenAI"` → `"Open A I"`, `"Claude"` →
`"Clawd"`, `"YouTube"` → `"You Tube"`. Never touches the stored transcript
or the text shown/logged elsewhere — only what's actually synthesized.

## 6. Caching

Not implemented in this phase — no real TTS provider exists to cache
output from (§3). The `SpeechSynthesisProvider` interface's streaming
shape doesn't preclude a future caching layer keyed on
`(text, language, voice_profile)`.

## 7. Verified

`tests/unit/test_voice_pronunciation.py` (6 cases); `MockTTS` exercised
end-to-end via the provider unit tests
(`tests/unit/test_voice_providers.py`).
