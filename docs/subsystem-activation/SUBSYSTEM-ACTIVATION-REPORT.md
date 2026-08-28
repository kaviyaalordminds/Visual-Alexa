# VEYRA Subsystem Activation Report

## Summary

This activation replaced static `system_settings` boolean flags with real,
verifiable health checks for AI, Voice, Vision, Computer Control, and IoT.
`GET /system` and the desktop status screen now report genuine subsystem
state — never a config-file-exists-so-it-must-be-connected guess. See
`app/services/subsystem_health.py` for the single source of truth every
check is defined in.

## Final status (this sandbox — a Linux container with no Windows, no
microphone, no GPU, and no real AI credentials supplied)

| Subsystem | Status | Why |
|---|---|---|
| AI | **NOT CONFIGURED** | No `VEYRA_AI_PROVIDER`/`MODEL`/`API_KEY`/`BASE_URL` set. |
| Voice | **NOT CONFIGURED** | No STT/TTS/wake-word provider declared, and this build has no real audio implementation regardless. |
| Vision | **DEGRADED** | OCR is genuinely available (tesseract installed); no vision *model* provider configured, so AI-driven scene understanding doesn't work — basic screen reading does. |
| Computer Control | **NOT ENABLED** | `computer_control.enabled` permission flag is off by default. |
| IoT | **NOT CONNECTED** | No device paired — the correct default per the task's own acceptance criteria. |

Every one of these is the honest, correct answer for this environment —
none is a limitation of the activation work itself. See each subsystem's
own `*-STATUS.md` for exactly what would need to change on a real Windows
machine with real credentials to light each one up for real.

## What "activated" means here, precisely

For each subsystem, activation means: (1) a real configuration surface
exists (env vars, following the repo's existing `VEYRA_`-prefixed
`Settings` convention — no duplicate config system was invented); (2) a
real, cheap, synchronous or explicitly-cached check computes its status —
never a guess; (3) `/system` and the desktop UI surface that status plus a
human-readable reason; (4) where a genuine user-triggerable diagnostic
action makes sense (AI, Voice), it exists as a real tool
(`system.ai_health_check`, `system.voice_health_check`) reachable through
the same `ToolRegistry -> PolicyEngine -> Executor -> AuditLog` path every
other tool already uses.

What activation deliberately did **not** do: rewrite the deterministic
planner to call a real LLM (out of scope — `ModelRouter`/`TaskPlanner`
remain untouched, per `docs/PHASE-9-AUDIT.md`'s own carried-forward
finding that general LLM-backed planning is a distinct, larger future
phase); implement a real STT/TTS/wake-word audio pipeline (would require
new audio-hardware dependencies with no clear justification here); build
a real vision *model* provider (same reasoning as AI — the seam exists,
nothing fake fills it); implement a concrete IoT `DeviceAdapter` for any
real protocol (the interface now exists in
`app/services/device_adapter.py`; CLAUDE.md's Phase 8 Stop Condition
still holds — no fake integration ships).

## Files changed

- `services/local-api/app/core/config.py` — `ai_provider`/`ai_model`/
  `ai_api_key`/`ai_base_url`, `stt_provider`/`tts_provider`/
  `wake_word_provider`, `vision_provider` settings fields.
- `services/local-api/app/services/agent/llm_provider.py` — added
  `health_check()` to the `LLMProvider` Protocol and
  `NotConfiguredLLMProvider`.
- `services/local-api/app/services/agent/providers.py` (new) —
  `CloudLLMProvider`, a real, generic OpenAI-compatible HTTP client (no
  vendor SDK), plus `build_llm_provider()`.
- `services/local-api/app/services/subsystem_health.py` (new) — the real
  per-subsystem status computation; the single `ComponentStatus` literal
  `/system` and its TypeScript mirror both import from here.
- `services/local-api/app/services/subsystem_diagnostics_tools.py` (new)
  — `system.ai_health_check` / `system.voice_health_check` tools.
- `services/local-api/app/services/device_pairing.py` —
  `has_any_active_permission()`, the real check IoT's status is derived
  from.
- `services/local-api/app/services/device_adapter.py` (new) —
  `DeviceAdapter` Protocol, no concrete implementation (see IOT-STATUS.md).
- `services/local-api/app/api/system.py` — wired to the real checks;
  `ComponentStatus` gained `DEGRADED`/`DISABLED` (additive); response
  gained an additive `details` map.
- `services/local-api/app/main.py` — structured `[AI]`/`[VOICE]`/
  `[VISION]`/`[COMPUTER]`/`[DEVICE]` startup logging using the same real
  checks; registers the two new diagnostic tools.
- `services/local-api/pyproject.toml` — `httpx` promoted from a dev-only
  test dependency to a core runtime dependency (CloudLLMProvider needs it;
  no new dependency was introduced, an existing one was reused).
- `packages/contracts/typescript/src/system.ts`,
  `apps/desktop/src/App.tsx`, `apps/desktop/src/index.css` — frontend
  contract + reason-text rendering.
- `.env.example` — documents the new variables (all blank by default).
- `services/device-gateway/README.md` — points at the new
  `DeviceAdapter` interface.

## Tests added

`tests/unit/test_cloud_llm_provider.py` (13 tests, real HTTP-call logic
against `httpx.MockTransport` — never a real network call, but the actual
request/response/error-handling code, not a hand-mocked substitute),
`tests/unit/test_subsystem_health.py` (18 tests covering every status
transition for every subsystem), `tests/integration/
test_system_subsystem_status.py` (4 tests proving `/system` reflects real
state changes end-to-end), `tests/integration/
test_subsystem_diagnostic_tools.py` (3 tests, including one that proves a
configured API key is never present anywhere in the tool's HTTP response
or its `AuditLog` row). Full suite: **740 backend tests passing** (was
702), ruff/mypy clean across all 5 Python packages, 66 frontend tests +
eslint + tsc clean.

## Live verification

Real backend started against a fresh database; structured startup logs
confirmed for all five subsystems; `GET /system` confirmed to return the
real states above with matching `details` reasons; both diagnostic tools
invoked live over the real `/tools/{id}/invoke` path; `computer_control`
flipped to `DISABLED` live by toggling the permission flag on this
non-Windows host, confirming the platform check is real, not cosmetic.
