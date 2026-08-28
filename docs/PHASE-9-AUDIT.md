# Phase 9 Audit — Integration, Orchestration & Reliability

Status: **Step 1 of the Phase 9 implementation order.** This document is a
factual inventory produced by direct code inspection (backed by six parallel
research passes covering backend core, the computer-control/vision/voice/
ai-runtime services, the agent/orchestration layer, the browser/integration/
IoT layer, the desktop frontend, and tests/docs/security posture). It
describes what the repository actually does today, not what it should
eventually do. Every claim below is grounded in a specific file and, where
useful, a line number, so it can be re-verified against the code at any time.

No code changes were made while producing this document, per the Phase 9
brief's Step 1 instruction.

---

## 1. Current architecture (as implemented)

VEYRA today is a single FastAPI process (`services/local-api`) that
in-process-imports four Python packages — `computer_control`, `vision`,
`voice`, and (conceptually) `ai-runtime` — none of which run as separate
services or over HTTP/subprocess boundaries. `services/ai-runtime` and
`services/device-gateway` are placeholder directories containing only a
`README.md` each; the real planner/orchestrator logic that "ai-runtime"
implies actually lives under `services/local-api/app/services/agent/`, and
the real IoT capability that "device-gateway" implies is a single in-memory
mock device (`app/services/mock_iot.py`).

Request flow: Desktop Shell (Tauri + React, `apps/desktop`) → Local API
(FastAPI, bound to `127.0.0.1:8756`) → `ToolRegistry` + `PolicyEngine` →
domain executors (computer-control / vision / voice / browser / mock-IoT) →
SQLite (`database/veyra.db`, Alembic-migrated) for all persistence. A
single in-process `EventBus` fans events out to WebSocket subscribers over
`ws://127.0.0.1:8756/events`. This matches the target shape in
`docs/architecture/01-SYSTEM-ARCHITECTURE.md` and the brief's final
principle diagram at the request-routing level; the gaps found below are in
depth of implementation (how much of the loop is real vs. templated/stubbed)
and in a handful of concrete reliability/honesty bugs, not in the overall
shape.

The startup-crash root cause from the immediately prior task ("no such table:
applications") is already fixed (commit `5af4776`): `database_url` is now an
absolute, cwd-independent path, and `app/db/migrate.py::ensure_database_ready()`
runs Alembic's migration chain as the first lifespan step, before anything
queries the database. That fix is not revisited here except where this
audit found it incomplete (see §4, P1-1).

---

## 2. Working components

Confirmed real (not mocked, not stubbed, not pretending) by direct code
reading:

- **Database & migrations** — one canonical, absolute-path SQLite file; a
  linear, gapless Alembic chain (`51aedcfad492` → … → `2a025fb1f8a8`); every
  model file has a corresponding migration; startup applies pending
  migrations automatically and idempotently.
- **Tool registry & Policy Engine** — `ToolRegistry.register()` genuinely
  rejects a tool with no `risk_level`/`required_permission`
  (`app/services/tool_registry.py:34-40`). `PolicyEngine.evaluate()`
  (`app/services/policy_engine.py:42-96`) is real, DB-backed grant lookup;
  CRITICAL-risk actions are hardcoded to never be satisfied by any stored
  grant (`policy_engine.py:64-69`), matching CLAUDE.md verbatim. Every tool
  invocation path — HTTP (`POST /tools/{id}/invoke`) and the agent
  orchestrator — goes through the single `execute_tool_call()` chokepoint
  (`app/services/tool_execution.py:36-157`); no bypass path exists.
- **Computer-control** — real Win32/UI-Automation backends under
  `services/computer-control/computer_control/windows/`, selected only when
  `sys.platform == "win32"`; on this Linux sandbox they correctly report
  "unsupported" rather than faking success. The evidence-tier priority order
  (native API → UI Automation → accessibility → app API → browser DOM → OCR
  → vision model → coordinate) is real, enforced in
  `packages/contracts/python/veyra_contracts/enums.py:57-71` and honored by
  the actual click/type dispatch; there is no coordinate-only fallback
  method on the mouse backend interface at all
  (`computer_control/core/backends.py:75-80`).
- **Vision / OCR** — `vision/ocr/engine.py` calls real `pytesseract` against
  real image bytes; `PerceptionFusion` (IoU-merge) is real deterministic
  logic. The vision *model* (ML/LLM-based element detection) is a real
  `Protocol` with only a `NotConfiguredVisionProvider` shipped — it reports
  unavailable, it never fabricates a detection.
- **Browser engine** — genuine Playwright/Chromium
  (`app/services/browser/adapter.py:229,238`), 29 registered browser tools,
  CAPTCHA/OTP/payment stop-conditions gating every state-changing action,
  and per-session isolation via UUID-keyed `SessionRegistry` where one
  session's failure or close never touches another.
- **Task orchestrator & state machine** — `AgentOrchestrator`
  (`app/services/agent/orchestrator.py`) runs a real
  RECEIVED→UNDERSTANDING→PLANNING→WAITING_PERMISSION→EXECUTING→OBSERVING→
  VERIFYING→COMPLETED loop, persisted to the `tasks`/`task_steps` tables,
  with transitions centrally validated by `TaskStateMachine.transition()`
  (`app/services/agent/state_machine.py:37-42`) — the orchestrator never
  writes `.state` directly. A `TaskBudget` (max_steps, timeout, max_recovery
  attempts, max_replans) is enforced, per CLAUDE.md.
- **Confirmation workflow** — fully wired end-to-end: a denied CRITICAL/
  confirmation-required step persists `confirmation_prompt`,
  `pending_tool_id`, `pending_plan`, publishes `TASK_CONFIRMATION_REQUIRED`,
  and `POST /tasks/{id}/confirm` resumes the *same* remaining plan rather
  than discarding it. TTL expiry and material-plan-change re-checks exist
  (`app/services/agent/confirmation.py`).
- **Recovery (partial, see §4)** — bounded, diagnostic retry via
  `RecoveryManager.decide()` (`app/services/agent/recovery.py:67-144`),
  correctly escalating PERMANENT→abort, RETRYABLE→retry→ask-user.
- **IoT device pairing** — `device_pairing.py` genuinely enforces
  PAIR→IDENTIFY→AUTHENTICATE→AUTHORIZE→REGISTER_CAPABILITIES→CONTROL in
  strict order (`_require_exact_previous`, lines 81-87), deny-by-default
  permission cache, and refuses to grant control over an unregistered
  capability. The only device is a clearly-labeled mock AC
  (`app/services/mock_iot.py`), matching CLAUDE.md's Phase 8 stop condition.
- **Credential storage** — never plaintext; `Fernet` + `PBKDF2HMAC`
  (390,000 iterations) on non-Windows, with a documented, intentionally
  `NotImplementedError` Windows-DPAPI stub (matches
  `docs/security/05-DATA-PROTECTION.md`'s stated design).
- **Frontend status display** — no fabricated "connected" state found
  anywhere in `apps/desktop/src`; every status label traces to a real field
  in the `/system` response, defaulting to a *disconnected*-looking value
  (not a connected one) before the first successful fetch. Avatar state is
  entirely event-driven off real `voice.ui_state.changed` WebSocket
  payloads — no timer/demo-based animation exists.
- **Frontend↔backend endpoint parity** — every endpoint
  `apps/desktop/src/api.ts` calls has a matching backend route; no orphaned
  frontend calls.
- **CORS / bind address** — `cors_origins` is the fixed allowlist
  (`tauri://localhost`, `http://localhost:1420`), never `*`; `host` defaults
  to `127.0.0.1` everywhere (config default, both `.bat` scripts); a
  repo-wide grep for `0.0.0.0` across `services/` and
  `apps/desktop/src-tauri` returns zero matches.
- **Test coverage breadth** — all 15 major subsystems named in the brief's
  own testing checklist have at least one real test file; skips are all
  environment-conditional (`DISPLAY`, `tesseract` binary, Playwright
  install), never a silent `xfail`; no test is disabled to force a pass.

---

## 3. Missing components (vs. the Phase 9 target)

These are not bugs in existing code — they are capabilities the Phase 9
brief describes that do not exist yet, and the code is honest about that
(returns an explicit "unavailable"/"capability unavailable" rather than
faking success):

- **General-purpose planning.** `TaskPlanner` (`app/services/agent/planner.py`)
  is an explicit, small, deterministic template matcher — its own docstring
  says so. Only three goals have real templates: `open_application`,
  `search_files`, `open_file`. `send_file`, `control_device`,
  `browser_task`, and `delete_files` all return `CAPABILITY_UNAVAILABLE`
  (`planner.py:61-67, 98-101`). **Concretely: neither of the brief's two
  headline end-to-end demonstrations — "open Chrome and search YouTube" nor
  "send this PDF to Arun on WhatsApp" — can complete today**, because
  `browser_task` and `send_file` are unimplemented planner capabilities, not
  because anything downstream is broken.
- **No real LLM provider.** `LLMProvider` is a real `Protocol`
  (`app/services/agent/llm_provider.py:27-37`) with only
  `NotConfiguredLLMProvider` shipped; `ModelRouter.route()` always returns
  `"deterministic"`. No vendor SDK is imported anywhere (repo-wide grep
  confirmed) — correct per CLAUDE.md, but it means "understanding" is
  pattern-matching, not comprehension.
- **No real STT/TTS/audio I/O.** All of voice's provider Protocols
  (`voice/providers/base.py:86-164`) ship only `NotConfigured*`
  implementations — no microphone capture, no wake word, no speech
  synthesis. The conversation-management logic around these (state machine,
  mishear correction, interruption handling) is real and tested, but has no
  real audio to operate on.
- **Memory is not consulted by planning.** `app/services/agent/context.py`
  explicitly documents that it never writes to or reads from the long-term
  `Memory`/`Workflow` tables — that's "a future phase" per its own comment.
  The brief's own example ("office folder" alias) is a real, working CRUD
  API today but is never looked up during target resolution — grep of the
  entire `agent/` package found zero references to the memory tables.
- **REPLAN recovery strategy is a stub.** `RecoveryManager` can decide a
  failure warrants re-planning, but the orchestrator's handling of that
  branch is hardcoded to fail the task — the code comment says so directly
  (`orchestrator.py:460-472`). Retry/re-observe recovery is real; recovery
  via genuine re-planning is not.
- **Real external integrations** (WhatsApp/Gmail/Spotify/etc.) and **real
  smart-home/IoT platforms** do not exist, by design (CLAUDE.md's Phase 8
  Stop Condition) — confirmed still true, and clearly labeled as such in
  code comments, not just in docs.
- **`GET /system/health`** in the exact shape the brief describes (nested
  `services: {...}` object with per-service state) does not exist. The
  closest equivalent, `GET /system`, has a different (flat) shape and — see
  §4 — does not perform live verification for several of its fields.
- **A rate-limiting layer** does not exist anywhere in the backend (grep
  found zero matches for any rate-limit pattern).
- **`docs/DATABASE.md`, `docs/DEVELOPMENT.md`, `docs/TROUBLESHOOTING.md`**
  have no equivalent anywhere in `docs/` (the other requested doc titles do
  have older, differently-named equivalents under `docs/architecture/` and
  `docs/security/`).

---

## 4. Broken / non-compliant components, prioritized

**P0 — application cannot start: none currently open.** The one known P0
(migrations never applied) was fixed in the immediately prior task and is
verified by `tests/integration/test_backend_startup.py` (10/10 passing,
real subprocess, real fresh database).

### P1 — core functionality broken or materially non-compliant with an explicit rule

**P1-1. `reconnect_all_on_startup` / `rebuild_permission_cache_on_startup`
are not actually fault-isolated, contradicting both their own inline
comment and CLAUDE.md's "optional subsystems must never block startup"
rule.** `app/main.py:92-96` comments that per-integration/per-device
failures are "already handled individually inside these two calls." But
`IntegrationRegistry.reconnect_all_on_startup`
(`app/services/integration_registry.py:169-195`) has no try/except around
the per-row loop — it only conditionally *skips* rows via `if`/`continue`
checks; an unexpected exception (e.g. from `tool_registry.register` or
`validate_credential`) propagates and aborts the whole startup sequence.
`DevicePairingService.rebuild_permission_cache_on_startup`
(`device_pairing.py:238-252`) has the identical gap. This does not fire in
normal operation today, but it is a real, silent landmine: one malformed
row in `integrations` or `devices` can take down the entire Local API on
next restart, in direct contradiction of the architecture's own stated
guarantee.

**P1-2. `/system` does not perform live verification for `database`,
`desktop`, or `local_api`, and several other fields are static config
flags, not live checks — this is exactly the failure mode the brief calls
out by name ("Do not report a component as CONNECTED merely because its
process exists").** `app/api/system.py:34-55`:
```python
desktop="CONNECTED",       # hardcoded literal
local_api="CONNECTED",     # hardcoded literal
database="CONNECTED",      # hardcoded literal — not an independent query
```
`ai`/`voice`/`vision`/`computer_control`/`iot`/`security` are read from a
boolean flag in the `system_settings` table (e.g. `"ai.configured"`), not
from any live ping of the subsystem itself. The only real DB interaction on
this path is the settings `SELECT` that already has to succeed for the
handler to return at all — so `database="CONNECTED"` happens to be *true by
accident of reachability*, not by design, and would keep reporting
CONNECTED even if a real health check (e.g. `SELECT 1` against a
connection-pool-level ping) would have caught a degraded-but-not-fully-dead
DB. This is the single most repeatedly emphasized failure mode across the
Phase 9 brief (§3, §29, §30, §41's "System health is truthful" /
"No fake success responses exist" acceptance criteria).

**P1-3. `execute_tool_call()` has no catch-all around `executor.execute()`,
so an unanticipated bug in any domain executor can silently skip the audit
log write CLAUDE.md calls an absolute rule ("every tool call writes exactly
one AuditLog row, success or failure").** `app/services/tool_execution.py:132`:
`result = await executor.execute(call)` is unguarded; domain executors only
catch specific typed exceptions they anticipate (`UnknownSessionError`,
`AdapterError`, `PathNotAllowedError`, etc.), none has a catch-all. This
requires a genuine executor bug to trigger — it is not observed to happen
today — but the invariant is not structurally guaranteed the way CLAUDE.md
requires.

**P1-4. WebSocket reliability does not meet the brief's explicit
requirements.** Neither side implements a heartbeat/ping — a silently-dead
TCP connection is invisible to both the frontend and backend until the OS
eventually notices. The frontend reconnect
(`apps/desktop/src/avatar/useAvatarSocket.ts:15,50-56`) retries every fixed
2000ms forever with no backoff and no attempt cap — not the "bounded
exponential backoff" the brief asks for by name (§16). It won't tight-loop
(2s floor), but it will hammer the port indefinitely if the backend is down
for an extended period, and it can't distinguish a temporarily-busy backend
from a genuinely dead one.

**P1-5. `EventBus` subscriber queues are unbounded — no backpressure or
drop policy for a slow/dead WebSocket client.** `app/core/event_bus.py`'s
`publish()` does `await queue.put(event)` per subscriber with no size cap;
one client that stops reading (dead socket the server hasn't noticed yet,
per P1-4) accumulates events in memory indefinitely rather than being
dropped or disconnected.

### P2 — important integration gaps (real, but lower blast radius than P1)

- **P2-1.** The desktop dashboard doesn't yet surface most of what already
  exists on the backend: `/tasks` (current task, progress, cancel/pause/
  confirm), `/memory`, `/conversations`, and the write-side of `/plugins`
  are all implemented server-side but never called from
  `apps/desktop/src/api.ts`. The brief's §29 dashboard requirements
  ("Current task", "Task progress", "Permission requests") are backend-ready
  but not yet frontend-visible.
- **P2-2.** The backend base URL/port (`8756`) is a duplicated literal in
  two separate frontend files (`api.ts:15`, `useAvatarSocket.ts:14`) with no
  single source of truth and no env-var override — changing the port
  requires editing two files by hand.
- **P2-3.** `.env.example` documents 7 of the 12 real settings in
  `Settings` — missing `cors_origins`, `credentials_store_path`,
  `filesystem_allowed_roots`, `browser_downloads_dir`,
  `browser_extension_origins`.
- **P2-4.** Cancellation is cooperative and checked only *between* discrete
  steps (`orchestrator.py:270-271, 588-624`) — a tool call already in
  flight (a running browser action, a running computer-control action)
  cannot be interrupted mid-call; cancellation only takes effect before the
  next step starts. Matches the brief's own honest framing risk ("Long-
  running tools must support cancellation where technically possible") but
  is a real gap against "Cancellation must propagate to... browser...
  computer control."
- **P2-5.** No dedicated cancellation test suite exists — the behavior is
  only exercised indirectly inside broader task-transition/API tests.

### P3 — non-critical

- Missing `docs/DATABASE.md`, `docs/DEVELOPMENT.md`, `docs/TROUBLESHOOTING.md`
  (older equivalents exist for the other requested titles under different
  paths/names).
- `scripts/dev-backend.bat` / `scripts/start-veyra.bat` (added in the prior
  task) are not yet mentioned in `README.md`.
- `start-veyra.bat`'s health-poll loop doesn't explicitly clear the status
  variable each iteration before calling curl — a curl-invocation failure
  (curl itself missing) could theoretically read a stale prior value;
  extremely unlikely (curl ships with Windows 10+) and not observed.
- `WindowsDPAPICredentialStore` is an intentional, documented
  `NotImplementedError` stub — correct for this phase, just noted for
  completeness.
- `services/ai-runtime` and `services/device-gateway` are placeholder
  directories (README-only) — correct/expected, not a defect.

---

## 5. Integration problems (cross-cutting summary)

Beyond the per-component findings above, the two largest structural
integration gaps are: (1) the planner cannot express most real user goals
yet (only 3 of the ~10 tool families have planning templates), so most of
the tool/execution/verification machinery below it — which is itself
solid — is currently reachable only through a narrow set of entry points;
and (2) the frontend and backend have diverged in surface area over Phases
1-8: the backend now exposes task orchestration, memory, and conversation
APIs that the frontend has no UI for at all.

## 6. Dependency problems

None found. No circular imports, no vendor SDK imported outside its
adapter, no duplicate service/registry/database instantiation anywhere
(confirmed during the backend-core and services passes).

## 7. Configuration problems

See P2-2 and P2-3 above. No other environment/configuration drift found;
`.env.example`'s existing 7 entries all match `Settings` field names and
`VEYRA_` prefix exactly.

## 8. Security problems

No urgent findings. CORS, loopback binding, deny-by-default IoT pairing,
CRITICAL-tier non-bypassability, and credential encryption are all
verified real and correct. The only two gaps are P1-3 (audit-log
invariant not structurally guaranteed under an executor bug) and the
absence of any rate-limiting layer (noted in §3 as a missing component,
not urgent given the API is loopback-only and single-user by design).

## 9. Database problems

None found beyond what the prior task already fixed. Migration chain is
linear and complete; every model has a migration; the canonical DB path
is absolute and cwd-independent; startup is idempotent against fresh,
stale, and up-to-date databases (regression-tested).

## 10. Runtime problems

P1-1 (startup can still be taken down by a bad integration/device row,
despite the code's own claim otherwise) is the only startup-time runtime
risk found. P1-4/P1-5 are steady-state runtime reliability gaps (dead
connections going undetected; unbounded memory growth under a specific
failure condition).

## 11. Recommended fixes (this phase's scope)

Per the brief's own §40 ("MAKE EXISTING COMPONENTS WORK TOGETHER
RELIABLY," not "implement every future feature"), Phase 9 code changes
following this audit will target the P1 items — they are well-scoped,
low-risk, and directly address the brief's most repeated concern (truthful
status, no silent startup failure, no silent audit-log gaps, bounded
WebSocket reliability):

1. Make `reconnect_all_on_startup` and `rebuild_permission_cache_on_startup`
   genuinely fault-isolated per item (P1-1).
2. Make `/system` perform real, independent verification for `database`
   (an explicit liveness query distinct from the settings read),
   `local_api`, and `desktop`, and stop presenting config-flag lookups as
   equivalent to a live check where feasible without breaking the existing
   response contract the frontend depends on (P1-2).
3. Wrap `executor.execute()` in `execute_tool_call()` with a catch-all that
   still writes the required `AuditLog` row before re-raising or returning
   a structured failure (P1-3).
4. Add a WebSocket heartbeat/ping (both directions) and switch the
   frontend's reconnect loop to bounded exponential backoff with a cap
   (P1-4).
5. Bound `EventBus` subscriber queues and define a drop policy for a
   client that stops reading (P1-5).

P2 items (frontend dashboard surface, config centralization, `.env.example`
completeness, mid-tool cancellation, cancellation test coverage) and P3
items (documentation set completion) are recorded above as backlog for a
follow-up pass; deep feature work (a real LLM-backed general planner,
memory-informed target resolution, true re-planning recovery, real STT/TTS
providers, real external integrations) is explicitly out of scope for this
phase per the brief's own boundary and CLAUDE.md's phase-gating rule, and is
listed here only so it's not lost.
