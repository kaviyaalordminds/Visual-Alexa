# Wake Word

## 1. Interface

`WakeWordDetector.process_chunk(audio_chunk: bytes) -> WakeWordActivation`
(`voice/providers/base.py`). `WakeWordActivation` (`voice/core/models.py`)
carries `detected`, `phrase`, and `confidence` — below-threshold
activations are filtered by the implementation itself, so a caller never
second-guesses a confidence it receives (brief §8-10).

## 2. Shipped implementations

- `NotConfiguredWakeWord` — never activates. The only real, non-mock
  implementation in this phase (`AUDIO-PIPELINE.md` §3).
- `MockWakeWord` (`voice/testing/mocks.py`) — activates only for one
  seeded chunk value, so tests can prove both a true wake ("Hey Veyra")
  and a false-activation resistance case (background noise/TV/music
  chunks that must never trigger) deterministically —
  `tests/unit/test_voice_providers.py::test_mock_wake_word_activates_only_on_seeded_chunk`.

## 3. Modes (brief §65)

`WakeWordMode` (`voice/core/enums.py`): `WAKE_WORD_ONLY` (default),
`PUSH_TO_TALK`, `VOICE_ACTIVATION`, `HYBRID`. Seeded in
`DEFAULT_SETTINGS["voice.mode"] = "WAKE_WORD_ONLY"`
(`app/db/seed_defaults.py`). `wake_word.enabled` starts `False` — no
listening happens until the user explicitly turns it on
(`docs/security/05-DATA-PROTECTION.md` §3).

## 4. Push-to-talk fallback (brief §65-68)

The mode enum already models `PUSH_TO_TALK`/`HYBRID`; a real
`VoiceHotkeyManager` binding an OS-level hotkey to
`VoiceConversationManager.start_session(activation_source=ActivationSource.HOTKEY)`
is real-but-unverifiable here for the same reason as the rest of
`AUDIO-PIPELINE.md` §3-4 — no OS-level hotkey capture exists to test in
this container. `ActivationSource.HOTKEY` is a real, tested enum value
(`voice/core/enums.py`) ready for that binding.

## 5. Real activation, no privilege change (brief §68)

Whichever `ActivationSource` starts a session, `start_session` produces
the exact same `VoiceSession` with the exact same permissions — activation
method never widens what a subsequent command can do (brief §131). Verified
by `tests/integration/test_voice_conversation.py` and the security suite
using the default `ActivationSource.API`, which exercises the identical
code path a real wake-word/hotkey activation would.
