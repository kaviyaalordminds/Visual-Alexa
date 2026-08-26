# Cloud Boundary

## 1. Off by default, checked before every use

`DEFAULT_SETTINGS["cloud_fallback.enabled"] = False`
(`app/db/seed_defaults.py`) — no cloud STT/TTS/LLM call is ever made
unless a user has explicitly enabled it. `stt.mode` defaults to `"LOCAL"`,
`stt.provider`/`tts.provider` default to `None` — there is no configured
cloud provider to even attempt calling out of the box.

## 2. The check a real cloud call must pass (brief §17-19)

1. Is a cloud provider actually configured (`stt.provider`/`tts.provider`
   non-`None`)?
2. Is `cloud_fallback.enabled` true?
3. Does `ConnectivityManager.cloud_features_available()` confirm
   `ConnectivityState.ONLINE` right now (`OFFLINE-MODE.md`)?
4. Does the privacy policy for this content allow it (secrets already
   redacted before anything is persisted — `VOICE-PRIVACY.md`)?

All four gates live in the caller (`app/services/voice`), never inside a
provider implementation — no `Protocol` in this phase has network access
of its own at all (`STT.md` §2, `TTS.md`).

## 3. What actually exists today

No real cloud provider adapter ships in Phase 5 — every `NotConfigured*`
provider does zero I/O by construction (`AUDIO-PIPELINE.md` §3). The
four-gate check above is therefore currently moot in practice (there's
nothing configured to gate), but the settings and `ConnectivityManager`
it depends on are real and tested, ready for a future provider adapter to
be wired in behind the same check.

## 4. Verified

`tests/security/test_phase5_voice_security.py::test_1_cloud_upload_requires_explicit_consent_off_by_default`;
`tests/unit/test_voice_connectivity.py` (5 cases, including a raising
checker never being treated as "online").
