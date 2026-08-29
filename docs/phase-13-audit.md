# VEYRA — Phase 13 Audit

Performed before any Phase 13 implementation, per its own explicit
instruction. Three parallel research passes covered: (1) the health-model
state vocabulary, task-model completeness, and event-bus coverage against
Phase 13's specific new asks; (2) idempotency, observability, AI-routing,
and offline-classification; (3) the command-center UI, the security/
confirmation UI, and startup ordering. This builds directly on
`PHASE_12_AUDIT.md` (published minutes before this phase's spec arrived)
rather than re-deriving the whole system from scratch — most of Phase
13's brief describes capability Phases 1-12 already built for real.

A separate, independent Phase 13 audit session ran concurrently and was
merged into this branch alongside this one — see
`docs/phase-13-runtime-validation-audit.md` for its distinct focus (live
verification of the AI health state machine's four states, the IoT
discovery-vs-authorization security boundary under a real pairing flow,
and a real CI gap it found and fixed: `tesseract-ocr` was never
installed in CI, breaking `services/vision`'s OCR-dependent tests on
every run). Its findings and this audit's are complementary, not
conflicting.

## 1. System health model

**Vocabulary**: current `ComponentStatus` = `CONNECTED, NOT CONFIGURED,
NOT ENABLED, NOT CONNECTED, ACTIVE, ERROR, DEGRADED, DISABLED`. Phase 13
wants `CONNECTED, READY, DEGRADED, DISCONNECTED, NOT_CONFIGURED,
DISABLED, ERROR, INITIALIZING`. Most map cleanly (spelling/naming only).
Two are genuinely new: **READY** has no equivalent (`ACTIVE` exists in
the type but is dead — never actually returned by any `compute_*_status`
function); **INITIALIZING** has no per-subsystem equivalent (only a
coarse, process-wide `is_ready()` boolean exists, not a per-subsystem
transient state).

**`SystemHealthManager`**: no such class exists, but its functional
equivalent does — five standalone `compute_*_status` functions in
`subsystem_health.py`, each independently real and tested. This is an
architecturally sound alternative, not a gap by itself.

**WebSocket health push**: `EventType.SYSTEM_HEALTH_CHANGED` is
*defined* (Phase 1) but has never been published anywhere in the
codebase — confirmed dead code. `GET /system` is pure polled REST.

## 2. Task model

Most Phase 13-requested fields map cleanly to real, existing columns
(`description`≈user_request, `normalized_goal`≈intent, `state`≈status,
`priority`/`started_at`/`completed_at`/`current_step`/`total_steps`
exact, `failure_reason`+`failure_category`≈error, `result` exact).

Three real gaps:
- **`plan`** is not reliably persisted as a `Task`-level field — it only
  lives transiently in `task.result` during `WAITING_PERMISSION`/
  `PAUSED`, and is overwritten (`task.result = {}`) once resumed. A
  completed task's plan is not retrievable from the row afterward
  (though every step's `tool_id`/`arguments` remain on `TaskStep` rows).
- **`confirmation_state`** is real but fully implicit (`state ==
  WAITING_PERMISSION` + `result.confirmation_prompt`), not an explicit
  field — acceptable as designed, but worth noting for anyone querying
  the API expecting a dedicated field.
- **`recovery_attempts`** is tracked in memory throughout a run
  (`TaskContext.retry_count`/`replan_count`) but is **never persisted**
  to the `Task` row — it's silently lost the moment a task reaches a
  terminal state. This is the one genuine, worth-closing gap here: the
  information exists and is computed correctly, it just isn't kept.

## 3. Event bus coverage

Real/clean matches for most of Phase 13's list (`task.created`,
`task.step.started/completed`, `task.completed/failed`,
`device.connected/disconnected`, Phase 12's `iot.device_*`,
`memory.updated`, `security.blocked`). Several map with naming drift
only (`task.planning`→`TASK_PLANNED`, `task.waiting_confirmation`→
`TASK_CONFIRMATION_REQUIRED`, `task.recovery`→split into `TASK_RECOVERY_
STARTED/COMPLETED`, `intent.detected`→`VOICE_INTENT_RECEIVED`,
`avatar.state_changed`→`VOICE_UI_STATE_CHANGED`, a deliberate Phase 6
design choice, not an oversight).

**Genuinely absent, no equivalent at all**: `computer.action`,
`computer.observation`, `browser.navigation`, `browser.action`,
`vision.capture`, `vision.result`, `memory.created` (only
`MEMORY_UPDATED` exists). Real gaps, but lower-priority than the health/
observability findings below — they'd add granularity to an already-real
event stream, not close a functional hole.

## 4. Idempotency (a genuine, exploitable-today gap)

`ToolCallRequest.call_id` already defaults to a fresh `uuid4()` per
construction — a real, unique-per-call identifier that could serve as an
idempotency key. Nothing today reads it for deduplication.

**This is not merely theoretical**: `AgentOrchestrator._call_tool`
builds a brand-new `ToolCallRequest` (and therefore a brand-new
`call_id`) on *every* invocation, including `RecoveryManager`'s own
`RETRY` strategy re-attempting the exact same failed step. If a tool's
underlying action actually succeeded server-side despite the caller
seeing a timeout/transient failure (the exact scenario Phase 13 §28
describes — "network temporarily fails after sending a message"), a
retry today would re-execute the action a second time with no way to
detect the duplicate. There's no real messaging integration yet to make
this concrete for messages specifically (moot there, per CLAUDE.md's
Phase 8 Stop Condition), but the mock IoT device-control tools
(`iot.mock_ac.set_power`/`.set_temperature`) are real, already-shipped
examples of exactly the "device action" case Phase 13 calls out, and
they have zero duplicate-call protection today.

## 5. Observability (a genuine, silently-broken existing feature)

`app/core/logging.py`'s `JSONFormatter` emits a fixed schema
(`timestamp, level, logger, message, correlation_id, exception`) —
missing `subsystem`/`task_id`/`event`/`duration`/`result` entirely, even
when a caller tries to supply them. Concretely: `app/api/tasks.py` calls
`logger.exception(..., extra={"task_id": task_id})` at three call sites
— but `JSONFormatter` never reads `record.task_id`, so that value is
silently discarded every time. Separately, `correlation_id` is backed by
a real `contextvar` (`set_correlation_id`/`get_correlation_id`), but
**`set_correlation_id` is never called anywhere in the codebase** — the
log-line `correlation_id` field is always `null` in practice, while the
*event-bus* `correlation_id` (threaded through ~20+ real call sites in
`orchestrator.py`/`tool_execution.py`) works fine. Two mechanisms with
the same name, one real and one dead. This is exactly the kind of silent
data loss CLAUDE.md's coding standards warn against ("no silent
exception swallowing," extended here to "no silently-dropped structured
log fields").

## 6. AI routing — already correct, not a gap

`intent.py` and `planner.py` remain 100% deterministic (re-confirmed,
zero LLM calls in either). A real `ModelRouter` class exists
(`model_router.py`) and always resolves to `"deterministic"` today,
by design, since no LLM provider beyond the diagnostic-only
`CloudLLMProvider` is wired into the planning path. Phase 13's "never
send routine intents through a cloud model" requirement is already fully
satisfied — not through explicit routing, but because nothing in this
path calls an LLM at all. No change needed.

## 7. Offline-first classification — real but low-leverage

Only a voice-scoped `ConnectivityManager` exists; no repo-wide
`LOCAL_ONLY`/`LOCAL_WITH_OPTIONAL_AI`/`CLOUD_REQUIRED`/
`INTEGRATION_REQUIRED` classification. Assessment: each subsystem's
already-real health status (`NOT CONFIGURED`/`DEGRADED`/etc.) already
dynamically communicates this per-feature at runtime. A static
classification enum would mostly restate that information at compile
time — genuinely additive only as a pre-flight check before attempting
an action, or for docs/onboarding. Low priority; not implemented this
phase.

## 8. Command-center UI and confirmation UI — both genuinely missing

- **Command center (§31)**: the backend's task API (`POST /tasks`,
  `GET /tasks/{id}`, `run`/`cancel`/`pause`/`resume`/`confirm`) is
  entirely real, but **the desktop frontend never calls any of it**.
  `apps/desktop/src/api.ts` has zero task-related types or calls;
  `DevConsole.tsx` only invokes five fixed, mostly read-only diagnostic
  tools directly via `POST /tools/{id}/invoke` — not task creation.
  There is no live task-progress display, no cancel/approve/reject/
  retry control, anywhere in the desktop app.
- **Confirmation UI (§32)**: the backend already builds a real, specific
  prompt (`ConfirmationManager.build_prompt` → `"{tool} — {target}.
  Risk: {level}. {reason} Continue?"`, never a vague "Allow?"), and
  `POST /tasks/{id}/confirm` is real — but nothing in the frontend
  renders `confirmation_prompt` or offers Allow/Deny controls.

These are the two highest-visibility gaps in this audit: VEYRA can run
a full plan → execute → observe → verify → recover cycle for real
through its HTTP API, but a user driving it through the desktop app
today has no way to start, watch, or approve a task at all — only the
narrow, low-level tool-invocation panel in `DevConsole.tsx`.

## 9. Startup orchestration — mostly matches, sound architecture

Actual order in `main.py`'s lifespan: Database (fatal on failure) →
Tool/Application/Computer-Control/Vision/Browser tool registration →
Integration reconnect + device-permission cache rebuild (fault-isolated,
confirmed real per the Phase 9 P1-1 fix) → Orchestrator + Voice manager
init → a logging-only subsystem-status pass → `mark_ready()`. No
distinct "Event Bus" or "Health Manager" startup phase exists as a named
step — the event bus is used implicitly (no init required) and health is
computed on demand rather than as a boot-time service object. This is a
different but coherent architecture, not a missing capability. Optional-
service fault isolation is real and re-confirmed.

## 10. Prioritization (P0/P1/P2 — see completion report for what was
actually implemented)

**P0 — real, bounded, high-value, implemented this phase:**
1. Real idempotency for step retries: a stable `call_id` reused across
   `RecoveryManager.RETRY` attempts of the same step, plus a bounded,
   TTL'd dedup cache in `execute_tool_call` that returns the cached
   result instead of re-invoking the executor for a repeated `call_id`.
2. Fix the observability gap: `JSONFormatter` now includes `task_id`/
   arbitrary structured `extra` fields instead of silently dropping
   them, and `set_correlation_id` is actually called around task
   execution so log lines during a run carry the real correlation ID.
3. Persist `recovery_attempts` (`retry_count`/`replan_count`) onto
   `Task.extra_metadata` at every terminal transition — closes the one
   real task-model gap found.
4. Publish `SYSTEM_HEALTH_CHANGED` for real: `GET /system` now tracks
   the last-computed status in memory and publishes a diff event when
   anything changes between polls — makes the previously-dead event
   type real.
5. A minimal, real Task Panel + Confirmation UI in the desktop frontend:
   create and run a task, poll its live progress, and render the real
   `confirmation_prompt` with working Allow/Deny controls — closes the
   two highest-visibility gaps (§8) without attempting the full
   command-center/security-dashboard polish (multi-task history,
   retry/inspect-details, ALLOW FOR THIS TASK vs. ALLOW ONCE
   distinction in the UI) that remains legitimate future work.

**P1/P2 — real, deferred with reasoning (not implemented this phase):**
- The remaining event-bus categories (`computer.*`, `browser.*`,
  `vision.*`, `memory.created`) — additive granularity, not a functional
  gap; deferred to avoid inventing publish points not tied to a real
  decision (unlike Phase 12's additions, several of these don't have an
  obvious single real chokepoint yet without further design work).
- `READY`/`INITIALIZING` health states and a `SystemHealthManager`
  facade class — the existing vocabulary and functional decomposition
  already work; renaming/wrapping them without a concrete consumer that
  needs the distinction would be process, not progress.
- A repo-wide offline-feature-classification enum — real but low-
  leverage per §7.
- The full command-center polish (task history list, retry/inspect
  buttons, ALLOW FOR THIS TASK scope in the UI) and a redesigned
  security dashboard — both correctly deferred in Phase 12 for the same
  reason (separately-scoped UI projects); this phase's minimal Task
  Panel is deliberately narrow, not a first draft of those.

**Explicitly out of scope, not deferred but refused:**
- Building real message-send idempotency for WhatsApp/email — no real
  connector exists (CLAUDE.md's Phase 8 Stop Condition), so there is
  nothing to make idempotent yet.

## 11. Additional real gaps found during live verification (P0-6/P0-7)

Live-verifying P0-5's Task Panel against a real running backend (per
this phase's own "text-first runtime testing" requirement) surfaced two
further real, small, security-relevant gaps beyond the five audited
above — fixed the same way as everything else in this phase: found,
fixed, tested, re-verified live.

- **P0-6 — "Create a folder called X" had no intent/planner route.**
  `filesystem.create_folder` has been a real, registered tool since
  Phase 2, but nothing in `IntentInterpreter`/`TaskPlanner` recognized
  natural-language "create a folder..." requests — one of Phase 13's own
  five named end-to-end tests would have returned `MISSING_INFORMATION`
  for real. Closed with a new intent pattern and `_plan_create_folder`
  template (default parent = the first configured allowed filesystem
  root, same concept `_plan_search_files` already uses). See
  `docs/testing/e2e.md`.
- **P0-7 — two permission-system correctness bugs, both security-
  relevant:**
  1. `RecoveryManager.decide()` had no classification for
     `ErrorCategory.PERMISSION_DENIED` at all, so a hard, non-
     confirmable denial (e.g. `computer_control.enabled` off) fell
     through to the generic "not a recognized recoverable category"
     ABORT — a confusing, internal-sounding `failure_reason` for what is
     actually an ordinary, expected denial. Fixed by adding it to
     `_PERMANENT_CATEGORIES` with a clear reason.
  2. **`ALLOW_ONCE` was not actually single-use.** `PolicyEngine.
     evaluate` matched and returned `allowed=True` for an `ALLOW_ONCE`
     grant but never revoked it afterward — it silently behaved
     identically to `ALLOW_SESSION` for its whole 5-minute TTL, letting
     a second, unrelated task reuse a confirmation the user believed was
     one-time-only. This directly contradicted the grant's own
     documented intent (`confirmation_actions.py`'s comment: "single-
     use... never a standing ALWAYS_ALLOW") and is the more significant
     of the two findings — a real trust gap between what a confirmation
     dialog implies and what the system actually enforced. Fixed by
     revoking the grant the moment it satisfies a check. See
     `docs/security/permissions.md` for the full writeup and
     `tests/unit/test_policy_engine.py`.

Neither finding was reachable through the existing test suite before
this phase — both were caught only by actually running the backend and
driving a real task through it by hand, which is exactly why Phase 13
asked for that step rather than treating "tests pass" as sufficient.
