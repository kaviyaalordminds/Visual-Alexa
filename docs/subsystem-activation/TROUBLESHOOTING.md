# Subsystem Activation — Troubleshooting

## "AI shows NOT CONFIGURED even though I set the env vars"

All four must be set together: `VEYRA_AI_PROVIDER`, `VEYRA_AI_MODEL`,
`VEYRA_AI_API_KEY`, `VEYRA_AI_BASE_URL`. `compute_ai_status()`
(`app/services/subsystem_health.py`) reports which ones are missing in
its `reason` string — check `GET /system`'s `details.ai` field, or the
`[AI]` startup log line, for the exact list.

## "AI shows DEGRADED forever, never CONNECTED"

`/system` never makes a network call on its own poll — DEGRADED means
"configured but not yet tested." Invoke the diagnostic tool explicitly:
`POST /tools/system.ai_health_check/invoke`. If that also reports
`reachable: false`, the `reason` field names the real cause (timeout, HTTP
status, DNS failure) — never a vague failure.

## "Voice never shows anything but NOT CONFIGURED, even with VEYRA_STT_PROVIDER set"

Expected. See `docs/subsystem-activation/VOICE-STATUS.md` — this build
has no real audio implementation wired in yet regardless of
configuration. Declaring a provider name only improves the *reason
text*, it does not change the status.

## "Vision shows DEGRADED, I expected NOT CONFIGURED or CONNECTED"

Check `details.vision` — it names exactly what's available (OCR,
capture) and what isn't (a vision model). DEGRADED is correct whenever
OCR or capture works but no model provider is configured; see
`docs/subsystem-activation/VISION-STATUS.md`.

## "Computer Control shows DISABLED, not NOT ENABLED, even though I turned the permission on"

That's the real platform check working. `DISABLED` means the permission
*is* on but the real Windows automation backends aren't available on this
machine's platform — `details.computer_control` names the platform. This
only resolves to `CONNECTED` on real Windows.

## "IoT never becomes CONNECTED"

Pair a device through the full lifecycle
(`POST /devices/pair` → `/identify` → `/authenticate` → `/authorize` →
`/register-capabilities` → `/permissions/grant`) — every stage is
required, in order (`docs/subsystem-activation/IOT-STATUS.md`). `NOT
CONNECTED` with zero paired devices is the correct default, not a bug.

## "The `system.ai_health_check` tool call hangs or times out"

The health check itself has a 3-second timeout
(`_HEALTH_CHECK_TIMEOUT_SECONDS` in `app/services/agent/providers.py`) and
never raises — a hang in the *tool call itself* (not the provider check)
points at something else (network egress blocked entirely, DNS
misconfigured for the whole container). Check the Local API's own logs
for the real exception.

## "I want to verify none of this is fake"

Read `app/services/subsystem_health.py` — every function is short and
readable; each one is either a real, cheap, synchronous check (platform
detection, `shutil.which`, a permission-cache lookup) or reads back the
result of a real check performed elsewhere (the AI reachability cache,
updated only by `providers.py`'s real HTTP calls). Nothing in this module
guesses.

## Related documentation

`docs/subsystem-activation/SUBSYSTEM-ACTIVATION-REPORT.md` (overview),
`AI-STATUS.md`, `VOICE-STATUS.md`, `VISION-STATUS.md`,
`COMPUTER-CONTROL-STATUS.md`, `IOT-STATUS.md` (per-subsystem detail),
`docs/PHASE-9-AUDIT.md` and `docs/phase-10/` (prior audits this work
builds on).
