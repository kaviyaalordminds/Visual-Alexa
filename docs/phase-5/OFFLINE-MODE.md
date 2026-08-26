# Offline Mode

## 1. `ConnectivityManager`

`voice/core/connectivity.py` — `check()` returns `ONLINE`/`OFFLINE`/
`UNKNOWN` from an injected `checker: Callable[[], bool] | None`. No
`LIMITED` value is ever produced by this manager on its own (a boolean
checker can't distinguish "degraded" from "up") — `ConnectivityState
.LIMITED` exists in the enum for a future, richer checker to report, and
callers must already treat it the same as `OFFLINE`/`UNKNOWN` (§2).

A raising checker, or no checker at all, is treated as `UNKNOWN` — never
silently assumed online. `cloud_features_available()` returns `True` only
for a confirmed `ONLINE` check.

## 2. What stays available offline

Everything under `voice/core/` — language detection, normalization,
interruption/confirmation classification, response generation, the state
machine, follow-up resolution — is pure Python with zero network
dependency. The entire `VoiceConversationManager` conversation loop, and
every tool Phase 2-4 already registered, works with zero connectivity;
none of it calls `ConnectivityManager` at all. Brief §56's "local
wake-word/VAD/STT/TTS continue offline" is true here by construction: no
provider in this phase does network I/O regardless of connectivity state
(`AUDIO-PIPELINE.md` §3).

## 3. Honest refusal for a cloud-only feature (brief §57)

There is no cloud-only feature implemented in Phase 5 to refuse yet (no
real cloud provider ships — `CLOUD-BOUNDARY.md` §3) — so this is
currently an unexercised code path in practice. The mechanism it would use
is real and tested: a caller checks `cloud_features_available()` before
attempting anything cloud-bound and, on `False`, must say so plainly
("That feature requires an internet connection.") rather than silently
failing or pretending to succeed — the same honesty discipline
`ResponseGenerator` already applies to task outcomes (`VOICE-PERSONALITY.md`
§2).

## 4. Verified

`tests/unit/test_voice_connectivity.py` — online/offline/no-checker/
raising-checker, all five cases.
