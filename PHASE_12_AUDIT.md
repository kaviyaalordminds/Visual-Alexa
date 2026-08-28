# VEYRA — Phase 12 Audit

Performed before any Phase 12 implementation, per its own explicit
instruction. Five parallel research passes covered: (1) desktop
frontend/dashboard/onboarding/security UI, (2) the AI provider system,
(3) the health API shape + event bus, (4) testing/packaging/versioning/
offline mode, (5) memory/data-classification/integrations/docs. Every
finding below is evidence-based (file:line), not assumed — a large
fraction of Phase 12's brief describes capability that Phases 1-11
already built for real. This document separates **REAL** (matches, no
work needed), **PARTIAL** (real underlying capability, different shape
or a genuine sub-gap), and **MISSING** (nothing exists).

## 1. Architecture map (unchanged, confirmed still accurate)

```
Desktop Shell (Tauri + React)
      │  HTTP + WebSocket, loopback only
      ▼
Local API (FastAPI) — the only process with DB access, the only
process that can invoke a tool
      │
      ├── Policy Engine (unconditional gate, every tool call)
      ├── Tool Registry (filesystem/application/window/browser/download/
      │     web.research/system diagnostics/IoT device/integration tools)
      ├── AgentOrchestrator (Intent → Plan → Execute → Verify → Recover)
      ├── EventBus + /events WebSocket
      ├── SubsystemHealth (real checks: AI/voice/vision/computer_control/
      │     IoT/database — NOT browser/memory, see §3)
      ├── IntegrationRegistry (pluggable, chokepoint-isolated)
      └── Database (SQLite via SQLAlchemy async, Alembic migrations,
            auto-applied at startup)
```

No structural change is needed here — every finding below is additive
(a missing field, a missing UI surface, a missing event) or a documented,
deliberate design choice, never a broken chain.

## 2. Service map / current runtime status

| Service | Status this audit | Evidence |
|---|---|---|
| Local API | REAL | `/health`, `/ready` both live-verified since Phase 10 |
| Database | REAL | Auto-migrating, tested fresh/stale/current cases |
| AI | PARTIAL | Real generic HTTP provider + health check; checks configuration+reachability but not "model available"/"minimal inference" (§4) |
| Voice | REAL (as designed) | Honest NOT_CONFIGURED when no audio pipeline exists |
| Vision | REAL (as designed) | Real OCR/capture detection |
| Computer Control | REAL (platform-gated) | Correctly reports NOT ENABLED off-Windows |
| Browser | REAL, but **not in `/system`** | Real Playwright engine (Phase 8); no health-check field exists (§3) |
| Memory | REAL CRUD, **not in `/system`** | Real API; no health-check field exists (§3) |
| IoT | REAL, deny-by-default | Full PAIR→...→CONTROL lifecycle enforced |
| Security/Policy Engine | REAL | Unconditional, CRITICAL non-bypassable |
| Integrations | REAL registry, no real connectors | Pluggable, chokepoint-isolated; only a reference (no-network) integration exists — correctly, per CLAUDE.md's Phase 8 Stop Condition |
| Event Bus | REAL for task/voice/assistant events; **absent categories** | See §3 Part B |
| Desktop Dashboard | PARTIAL | 9 of 12 requested cards; no timestamps/actions (§5) |

## 3. Health API and Event Bus (audit agent 3)

**`GET /system`** (`app/api/system.py`) already returns real,
individually-checked status for `desktop, local_api, database, ai, voice,
vision, computer_control, iot, security` plus `details{}`, `version`,
`uptime_seconds` — genuinely computed, not static (confirmed against
`subsystem_health.py`'s own docstring and the real SQL round-trip for
`database`).

**Real gaps** (not just naming):
- No `browser` or `memory` field in `/system` at all.
- No per-service `platform`, `latency`, or `last successful check`
  timestamp — `details{}` carries reason strings instead, which is
  honest but not equivalent.
- No `/api/v1/` prefix — every router is unversioned (confirmed: zero
  `prefix=` hits in `main.py`'s router registration).

**Event Bus** (`veyra_contracts.enums.EventType`): real, published events
exist for `task.*` (created/started/step.started/step.completed/
step.failed/completed/cancelled/failed) and `voice.*`/`assistant.*`
(listening_started, transcript.final, intent.received, thinking,
planning, completed). **Genuinely absent at the definition level** (not
merely unpublished): `computer.action_*`, `browser.*`, `vision.*`,
`avatar.state_changed` (avatar state reuses `voice.ui_state.changed`, a
deliberate Phase 6 design choice, not a gap), `permission.requested/
approved/denied`, `security.warning/blocked`, `iot.device_connected/
disconnected/command_started/command_completed` (only generic, non-IoT-
namespaced `device.connected/disconnected` exist), `integration.
connected/disconnected`, `memory.updated`, `audit.record_created`.

## 4. AI Provider System (audit agent 2)

Real: a single, generic, vendor-SDK-free `CloudLLMProvider`
(`app/services/agent/providers.py`) speaking the OpenAI-compatible HTTP
protocol — works against OpenAI itself, Ollama's `/v1` shim, LM Studio,
and any compatible gateway, configured via `VEYRA_AI_PROVIDER`/
`VEYRA_AI_MODEL`/`VEYRA_AI_API_KEY`/`VEYRA_AI_BASE_URL`.

**Assessment, not just a gap list**: Phase 12's named
`AnthropicProvider`/`OpenAIProvider`/`GeminiProvider`/`OllamaProvider`
hierarchy is **partially redundant** with the existing design — the
generic approach already satisfies CLAUDE.md's "no vendor SDK outside an
adapter module" rule more strongly (zero vendor SDKs at all, vs. a
per-class pressure to eventually add them) and already gives provider
flexibility via configuration alone. It is **not fully redundant**,
though: true native Anthropic/Gemini APIs are not OpenAI-compatible
chat-completions endpoints, so `CloudLLMProvider` genuinely cannot reach
them natively today — only OpenAI-compatible surfaces (including
Ollama). Rebuilding this into named classes now, without a concrete need
for native Anthropic/Gemini support, would violate CLAUDE.md's "never
rewrite a working module without justification" — **deferred**, not
implemented this phase (see §8).

The AI health check (`system.ai_health_check`) verifies (1) configured
and (2) reachable (folding in credential-rejection handling), but
deliberately never performs a billable "minimal inference" call
(documented in the tool's own description) and does not check whether
the *configured model* actually appears in the provider's `/models`
listing. The inference-avoidance is a deliberate, reasonable cost
tradeoff (unchanged this phase); the model-listing check is a real,
bounded, zero-cost gap worth closing.

## 5. Desktop Frontend (audit agent 1)

- **Dashboard cards**: 9 of 12 requested areas rendered (`desktop,
  local_api, database, ai, voice, vision, computer_control, iot,
  security`); no dedicated BROWSER/FILES/APPLICATIONS/MEMORY/
  INTEGRATIONS cards (browser has a separate diagnostic panel, not a
  unified status card). No "last checked" timestamp, no action button.
- **WebSocket state**: `useAvatarSocket.ts` only exposes a boolean
  `connected` — CONNECTING and RECONNECTING are indistinguishable from
  DISCONNECTED in the UI, despite real backoff/reconnect logic existing
  internally. This is a real, bounded, high-value gap (Phase 12 §6
  explicitly names these five states).
- **Onboarding wizard**: MISSING entirely — no code exists.
- **Security dashboard**: `PlatformPanel.tsx` is explicitly a diagnostic
  test harness (per its own comment), not a polished security
  dashboard — it does provide real Connect/Disconnect and Grant/Revoke
  controls, but no local-only-mode indicator, no audit-history view, no
  blocked-actions list, no CLEAR AUTHORIZATION/DISABLE FEATURE buttons.
- **Console logging discipline**: REAL — zero `console.*` calls in the
  reconnect path; no spam risk.

## 6. Memory, Data Classification, Integrations, Docs (audit agent 5)

- **Memory**: real per-record view/edit/delete + category filter on
  list. No bulk "clear all" or "disable a category" endpoint — a real,
  small gap. Zero automatic-memory-write code paths exist anywhere in
  the codebase today, so "sensitive info must not automatically become
  memory" is trivially true (nothing writes automatically at all) — not
  evidence of a defense that would survive a future auto-memory feature,
  worth noting but not an active gap to close now.
- **Data classification** (PUBLIC/NORMAL/PRIVATE/SENSITIVE/CRITICAL for
  *data*, distinct from the existing `RiskLevel` which classifies
  *actions*): genuinely MISSING as a formal, repo-wide system. A scoped
  `PrivacyLevel` exists only inside the vision pipeline; `audit.py`'s
  `SENSITIVE_FIELD_HINTS` does redaction, not classification.
- **Integrations**: the pluggable `IntegrationRegistry` (Phase 7) is
  real and chokepoint-isolated (every integration tool registers into
  the *same* `ToolRegistry`/Policy Engine, confirmed in code, not just
  documentation). Literal `integrations/{whatsapp,calendar,spotify,
  youtube}/` folders with real connectors do **not** exist and — per
  CLAUDE.md's Phase 8 Stop Condition ("no real Gmail/WhatsApp/Spotify
  integration... ships anywhere in this codebase") — **must not** be
  built this phase; Phase 12's own text lists these as "Future
  integrations," consistent with that boundary.
- **Docs**: real content exists for architecture/security/permissions/
  ai/voice/vision/computer-control/memory/iot/integrations, organized as
  numbered files under `docs/architecture/`, `docs/security/`,
  `docs/phase-*/`, `docs/agent/` rather than Phase 12's flat
  single-topic filenames. Installation/deployment/troubleshooting/
  testing content exists partially (`docs/phase-10/PRODUCTION-RUNBOOK.md`
  covers a lot of "troubleshooting"/"deployment") but not as
  standalone, named files matching Phase 12's exact list.

## 7. Testing, Packaging, Versioning, Offline (audit agent 4)

- **Testing**: 108 test files (63 unit, 27 integration, 14 security, 1
  agent-eval, 1 minimal end-to-end). Real coverage for nearly every
  Phase 12 e2e scenario exists, but scattered across unit/integration
  suites rather than named end-to-end tests; a full "restart VEYRA" cycle
  and real desktop app launch remain untested (the former needs a
  process supervisor that doesn't exist yet — a pre-existing, already-
  documented Phase 10 gap; the latter needs a GUI/Windows host).
- **Failure injection**: strong coverage for AI-unavailable, malformed
  responses, tool timeout, application/file missing, and permission
  denial. No dedicated "database unavailable" or "IoT disconnected" test
  by that name (though `test_mock_iot.py` exists and may cover related
  ground).
- **Packaging**: honestly documented as blocked on a Windows machine
  (`docs/phase-10/RELEASE-CHECKLIST.md`) — unchanged, not fake.
- **Auto-update**: MISSING entirely — correctly, since no Windows build
  exists yet to update (sequencing, not neglect).
- **Versioning**: `BACKEND_VERSION` exists, cross-checked against every
  manifest by a real test; no unifying `VEYRA_VERSION` symbol and no
  `/api/v1/` prefix.
- **Offline mode**: real, scoped `ConnectivityManager` exists for voice
  (`docs/phase-5/OFFLINE-MODE.md`); no general AI-task offline-detection
  concept — `CloudLLMProvider` fails naturally when unreachable, which
  the health check already surfaces as DEGRADED/ERROR rather than a
  proactive "offline" state.

## 8. Prioritized recommendations (P0/P1/P2 — see completion report §implementation for what was actually done)

**P0 — real, bounded, high-value, implemented this phase:**
1. Expand `EventType` with the genuinely-missing categories
   (`permission.*`, `security.*`, `iot.device_*`/`iot.command_*`,
   `integration.*`, `memory.updated`, `audit.record_created`) and wire
   publishing at the real, already-existing decision points (Policy
   Engine, browser stop-conditions, device pairing, integration
   registry, memory API, audit-log writer) — closes the largest, most
   structural gap this audit found.
2. Add `browser` and `memory` fields to `GET /system`, backed by real
   checks (browser: does the manager have live sessions / can a session
   be created; memory: a real DB round-trip), matching the pattern every
   other subsystem already uses.
3. Surface real WebSocket connection state (CONNECTED/CONNECTING/
   RECONNECTING/DISCONNECTED/ERROR) in the desktop frontend — the
   backend's reconnect/backoff logic is already real, this closes the
   "the UI can't tell them apart" gap Phase 12 explicitly names.
4. A bulk memory-clear endpoint (`DELETE /memory` with an optional
   `category` filter) — small, real, closes a named Phase 12 gap.

**P1 — real, bounded, deferred with reasoning (not implemented this
phase; recommended for a focused follow-up):**
- AI health check "model available" verification (list `/models`,
  confirm the configured model appears — zero-cost, no inference call).
- Dashboard cards for BROWSER/FILES/APPLICATIONS/MEMORY/INTEGRATIONS,
  each with a "last checked" timestamp (needs the `/system` timestamp
  field this phase doesn't add, to avoid scope creep beyond the two
  fields in item 2 above).
- A dedicated end-to-end test file consolidating the 10 named Phase 12
  scenarios (coverage exists, just scattered).

**P2 — real, but large/separate projects; explicitly not attempted this
phase (see completion report "known limitations"):**
- First-run onboarding wizard (a substantial, separate UI feature).
- A redesigned security dashboard (local-only-mode indicator, audit
  history view, blocked-actions list, CLEAR AUTHORIZATION/DISABLE
  FEATURE buttons) beyond the existing `PlatformPanel` diagnostic
  controls.
- A formal `DataClassification` enum — would need real integration work
  (memory/audit/integration payloads) to be meaningful, not just an
  unused enum.
- `/api/v1/` route versioning — cosmetic with no current external
  consumers; deferred until a real compatibility need exists.

**Explicitly out of scope, not deferred but refused:**
- Named per-vendor AI provider classes (Anthropic/OpenAI/Gemini) without
  a concrete native-API need — would rewrite a working, arguably
  *stronger* design without justification (CLAUDE.md).
- Any real WhatsApp/Spotify/Calendar/YouTube/Gmail connector — forbidden
  by CLAUDE.md's Phase 8 Stop Condition regardless of Phase 12's own
  "future integrations" list naming them.
- Auto-update architecture — no Windows build exists yet to update
  (would be built on nothing).
