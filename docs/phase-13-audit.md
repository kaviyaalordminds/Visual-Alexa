# Phase 13 Audit — Production Integration, Reliability & Runtime Capability Validation

## 0. Scope of this audit

Phase 13's brief (this repo's CLAUDE.md + the Phase 13 task prompt) asks
for a full architectural rebuild across 45 areas (orchestrator, task
model, tool registry, policy engine, avatar, voice pipeline, IoT, etc.).
Phases 1–12 already built essentially all of that architecture — this is
not a greenfield repo. What this audit actually found, and what this
session actually did, is narrower and more useful than re-deriving
45 sections from scratch:

1. **Audit**: confirm what phases 1–12 built is real, wired together, and
   currently working (not just present as files).
2. **Validate and fix** the one concrete, testable ask in this session's
   task — that `GET /system` and its `details` reasons report the true,
   live state of AI / Voice / Vision / Computer Control / IoT, never a
   guess, and that the IoT security boundary (discovery ≠ authorization)
   actually holds under a real pairing flow, not just in a unit test.
3. **Fix what's actually broken.** One real defect was found (below) and
   fixed. Nothing else in the 795-test suite was broken.

Prior audits remain the historical record and are not repeated here:
`docs/PHASE-9-AUDIT.md`, `docs/phase-10/PRODUCTION-READINESS-REPORT.md`,
`docs/phase-10/ARCHITECTURE-AUDIT.md`,
`docs/subsystem-activation/SUBSYSTEM-ACTIVATION-REPORT.md` (the session
immediately prior to this one, same day — see git log `0e75c87`).

## 1. Current architecture (confirmed present and wired)

```
Desktop Shell (Tauri + React, apps/desktop)
        |  HTTP + WebSocket, loopback only (127.0.0.1:8756)
        v
Local API (FastAPI, services/local-api) — the only DB-owning process
        |
        +-- app/api/*        17 route modules (system, tools, devices,
        |                     tasks, browser, voice, memory, permissions,
        |                     settings, plugins, integrations, events, ...)
        +-- app/services/agent/   orchestrator.py, planner, confirmation.py,
        |                         llm_provider.py + providers.py (real HTTP
        |                         client, no vendor SDK)
        +-- app/services/policy_engine.py   risk tiers -> permission check
        |                                   -> confirmation -> audit, every
        |                                   tool call, no bypass path
        +-- app/services/tool_registry.py   central registry, every tool
        |                                   declares risk/permission/schema
        +-- app/services/device_pairing.py  strict 6-stage IoT lifecycle
        +-- app/services/subsystem_health.py  real per-subsystem checks
        +-- app/core/event_bus.py           internal pub/sub, WebSocket
        |                                   fan-out to desktop
        +-- app/models/task.py              Task + TaskStep, states,
                                             plan/observations/tool_calls
        v
computer-control / vision / voice packages (services/*) — real
Playwright browser engine (Phase 8), real Windows UI Automation adapter
(Windows-only, Phase 2), real tesseract OCR (Phase 3), no real STT/TTS/
vision-model/LLM-planner implementation (all real seams, all honestly
NOT CONFIGURED until a provider is wired in)
```

This matches CLAUDE.md's non-negotiable shape: desktop talks only to the
Local API, the Local API is the only DB-owning and only tool-invoking
process, every tool call passes through the Policy Engine.

## 2. Working components (verified live this session, not just by reading code)

Verified by actually starting the Local API against a fresh database and
exercising the real HTTP API — not by reading source and assuming:

- **Startup**: migrations run automatically on a fresh DB (9 revisions,
  head `2a025fb1f8a8`), structured `[AI]`/`[VOICE]`/`[VISION]`/
  `[COMPUTER]`/`[DEVICE]` startup log lines, `Local API: READY` in
  under half a second.
- **`GET /health`**, **`GET /ready`**, **`GET /system`**: all real,
  respond correctly.
- **AI health state machine** — all four states confirmed live, not just
  in unit tests: `NOT CONFIGURED` (no env vars) -> `DEGRADED` (configured,
  never tested) -> `ERROR` (real HTTP 401 from a local mock provider with
  a wrong key) -> `CONNECTED` (same mock provider, correct key, real
  `GET /models` round-trip). The `system.ai_health_check` tool call that
  drives this transition wrote a real `AuditLog` row each time, with no
  API key anywhere in the row.
- **IoT security boundary** — the actual finding this task asked for.
  Ran a real device through the full HTTP API: `POST /devices/pair` ->
  `/identify` -> `/authenticate` -> `/authorize` -> `/register-capabilities`
  -> `/permissions/grant`. `/system`'s `iot` field stayed `NOT CONNECTED`
  after every stage up through `REGISTER CAPABILITIES` — registering a
  capability is not the same as granting permission to use it — and only
  flipped to `CONNECTED` after the explicit `grant` call. Revoking the
  permission flipped it back to `NOT CONNECTED` immediately. Attempting
  to call `/authorize` before `/authenticate` was rejected with HTTP 400
  (`PairingStageError`) — stage-skipping is genuinely not possible, not
  just documented as forbidden.
- **Computer Control** — `NOT ENABLED` by default; after explicitly
  flipping the `computer_control.enabled` setting on this Linux
  container, correctly reports `DISABLED` ("Windows UI Automation
  backends are unavailable on this platform") rather than a false
  `CONNECTED`.
- **Vision** — `DEGRADED`, with OCR and screen-capture reported as two
  independent capabilities in the reason text (not one combined boolean).
- **Backend test suite**: 795 passed, 3 skipped (platform-gated, e.g.
  Windows-only paths), 0 failed. `ruff check` and `mypy` clean across all
  5 Python packages (contracts, computer-control, vision, voice,
  local-api — 108 source files in local-api alone).
- **Frontend status dashboard** (`apps/desktop/src/App.tsx`) polls
  `GET /system` every 5s, renders every field's live value and reason
  text, has no hard-coded `CONNECTED`/`NOT CONFIGURED` strings (only CSS
  class-name comparisons against the live value, plus an honest
  `NOT CONNECTED` fallback while the very first poll is in flight), and
  shows "Local API unreachable: ..." rather than crashing when the
  backend is down.

## 3. Broken components found — and fixed this session

**CI never installed `tesseract-ocr`.** `services/vision`'s OCR engine is
real (`pytesseract` + the system `tesseract` binary), and 6 tests
(`tests/unit/test_ocr_engine.py`, `tests/integration/
test_vision_tools_api.py::test_ocr_extract_real_text`, two security tests
covering OCR-confidence-never-upgraded and OCR-text-treated-as-inert-data)
depend on a real `tesseract` binary on `PATH`. `.github/workflows/ci.yml`'s
`python` job never installed it, so these 6 tests would fail on every CI
run (confirmed: this sandbox had no `tesseract` installed either, and the
exact same 6 tests failed here before it was installed). This is a real,
previously-undetected gap — the tests were correct, CI's environment was
incomplete. Fixed: `ci.yml` now runs `apt-get install -y tesseract-ocr`
before the Python package install step; README's Prerequisites section
now documents the same system dependency for local development. Verified
fix: installed `tesseract-ocr` in this sandbox, reran the 6 previously-
failing tests (all pass) and the full suite (795 passed, 0 failed, ruff/
mypy clean).

No other failing test, lint error, or type error was found in the current
`main`-derived state of this branch.

## 4. Partially implemented / honestly incomplete (by design, not oversight)

These are real seams with no fake implementation behind them — correct
per CLAUDE.md's Phase 8 Stop Condition and this task's own "never insert
fake credentials" / "clearly report NOT_CONFIGURED" instructions, not
regressions:

- **AI**: `CloudLLMProvider` is a real, generic OpenAI-compatible HTTP
  client (no vendor SDK) and is fully wired to `/system` and the
  `system.ai_health_check`/diagnostic tools. It is deliberately **not**
  wired into the deterministic task planner (`app/services/agent/
  orchestrator.py` still resolves intents/plans without an LLM call) —
  carried forward from `docs/PHASE-9-AUDIT.md`. A user who configures
  `VEYRA_AI_*` gets a real, verifiable connectivity check; they do not
  yet get LLM-backed planning.
- **Voice**: no real STT/TTS/wake-word audio pipeline exists in this
  build. `compute_voice_status` honestly reports `NOT CONFIGURED`
  regardless of what provider name is declared, rather than pretending a
  declared intent is a working pipeline.
- **Vision**: OCR and screen-capture are real; no real vision-*model*
  (scene understanding) provider exists.
- **IoT**: the full 6-stage pairing/authorization lifecycle is real; the
  only thing that can be paired today is `app/services/mock_iot.py`'s
  single mock AC (clearly labeled mock-only, in-memory, no real
  network/hardware access). `app/services/device_adapter.py`'s
  `DeviceAdapter` Protocol is the seam a real Matter/Home Assistant/
  vendor-API adapter would implement — no concrete adapter ships.
- **Computer Control**: the Windows UI Automation adapter is real but,
  correctly, cannot be verified as `CONNECTED` on this non-Windows
  sandbox — it reports `DISABLED` with the actual reason, never a guess.

## 5. Missing integrations

Per CLAUDE.md's own Phase 8 Stop Condition, still correctly absent: real
Gmail/WhatsApp/Spotify integrations, a packaged browser extension, real
smart-home/Matter/Home Assistant connectivity, long-term personal memory,
autonomous background behavior. `app/services/integration_registry.py`
and `app/services/reference_integration.py` provide the modular interface
these would plug into; none is faked in the meantime.

## 6. Security concerns

None found this session beyond what prior audits already tracked. Live-
verified this session specifically: the IoT discovery-vs-authorization
boundary (§2 above) holds under a real pairing flow; a configured AI
provider's API key was never present in any HTTP response body or
`AuditLog` row across 4 real tool invocations; stage-skipping in the
device pairing lifecycle is rejected at the API layer (HTTP 400), not
just discouraged by convention.

## 7. Reliability concerns

The CI gap in §3 was the only one found. Optional-subsystem startup
(`AI`/`Voice`/`Vision`/`Computer Control`/`IoT` all failing to configure)
does not block Local API startup — confirmed live (`[VEYRA] Local API:
READY` printed with 4 of 5 optional subsystems `NOT CONFIGURED`/
`NOT ENABLED`/`NOT CONNECTED`).

## 8. Performance concerns

Not specifically profiled this session (out of scope for the runtime
capability activation task). `/system`'s own health checks are
deliberately synchronous/cached and never make a network call on their
own 5s poll cycle (AI connectivity is checked only on explicit
`system.ai_health_check` invocation) — this is a correctness property as
much as a performance one, and was verified live in §2.

## 9. Technical debt

None newly introduced this session. The one debt item fixed (§3) was pure
CI infrastructure, not application code.

## 10. Recommended fixes / next steps

1. Wire `CloudLLMProvider` into the actual task planner behind an
   explicit opt-in setting, so a configured AI provider does more than
   pass a health check — tracked as an existing carried-forward item, not
   new to this audit.
2. A real STT/TTS provider adapter (e.g. a local Whisper/Piper pair or a
   cloud STT/TTS API) is the next concrete step to move Voice off
   `NOT CONFIGURED` for real, matching the same "real check, no fake
   status" bar this session held AI/Vision/IoT to.
3. A first real `DeviceAdapter` implementation (Matter is the most
   broadly useful) would let IoT `CONNECTED` mean something beyond the
   existing mock AC, without touching the authorization boundary itself.
4. The full 45-step Phase 13 brief (task model polish, avatar-state event
   wiring end-to-end, browser agent hardening, etc.) is a multi-session
   effort layered on top of an already-substantially-complete Phases
   1–12 foundation — this audit's job was to establish that the
   foundation is honest and correct before any of that continues, per
   the brief's own "do not continue until the audit is complete."
