# 14 — Task Lifecycle

## 1. State machine

```
RECEIVED
   │
   ▼
UNDERSTANDING ──────► (ambiguous?) ──► WAITING_USER
   │
   ▼
PLANNING
   │
   ▼
WAITING_PERMISSION ──► (denied) ──► FAILED
   │ (granted)
   ▼
EXECUTING
   │
   ▼
OBSERVING
   │
   ▼
VERIFYING ──► (verified OK) ──► COMPLETED
   │
   │ (verification failed)
   ▼
RECOVERING ──► (retry budget available) ──► PLANNING
   │
   │ (budget exhausted / unrecoverable)
   ▼
WAITING_USER  or  FAILED

Any state ──► CANCELLED  (explicit user or system cancellation)
```

## 2. Guardrails (product brief §28 — mandatory, not optional)

Every task execution is bounded by a `TaskBudget`:

```
TaskBudget
  max_steps: int
  timeout_seconds: int
  max_recovery_attempts: int
  cancellation_token: CancellationToken
```

No autonomous loop may run without all four fields populated. The Task
Runtime rejects a task definition missing a budget — this is enforced in
code (`packages/contracts` validation), not left to convention. Exceeding
`max_steps` or `timeout_seconds` forces a transition to `FAILED` with a
clear `ErrorInfo` explaining the budget was exhausted, never a silent hang.

## 3. Recovery is diagnostic, not blind retry

On entering `RECOVERING`, the Task Runtime must determine, before deciding
to retry/replan/ask/fail:

- What step failed, and what was the tool's `ErrorInfo.code`?
- Is the error `retryable` (per the error model —
  `docs/security` error categories are shared with this lifecycle)?
- Did the UI/evidence change since the last observation (via
  `TemporalStateComparator`, `07-VISION.md`)?
- Is the target application/window/device still available?
- Did permissions change since planning (a grant could have expired)?

Only after this diagnosis does the runtime choose RETRY, REPLAN (back to
PLANNING with updated context), WAITING_USER (ask), or FAIL SAFELY
(terminal FAILED with full diagnostic `ErrorInfo`).

## 4. Mapping to events and avatar state

Every `TaskState` transition publishes a corresponding event
(`12-EVENTS.md`), which the avatar architecture (product brief §16) consumes
1:1 (e.g., `EXECUTING` → avatar EXECUTING state, `WAITING_PERMISSION` →
avatar WAITING_CONFIRMATION state). This mapping is why the state machine is
specified precisely rather than left as a loose set of status strings.

## 5. Phase 1 scope

Delivered: the full `TaskState` enum, transition rules, `TaskBudget`
contract, and unit tests validating legal/illegal transitions. Not
delivered: a live runtime executing real tasks through real tools — the
state machine is exercised by tests with synthetic transitions, not by a
real planner/executor yet.

## 6. Phase 4: a real runtime, and eight new transitions

`docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md` delivers the live runtime
this section anticipated: `AgentOrchestrator` drives real tasks through
real Phase 1-3 tools, exercising this exact state machine — no parallel
one. Real end-to-end execution surfaced eight legal transitions this
diagram didn't originally have (ambiguity discovered mid-plan,
confirmation needed mid-execution, human-in-the-loop pause, direct
recovery/failure edges from `EXECUTING`, resume-without-replan, and a new
`TIMED_OUT` terminal state distinct from `FAILED`) — see
`docs/phase-4/TASK-STATE-MACHINE.md` for the full list and the specific
real bugs this caught. `TaskBudget` gained `max_replans`; `TaskStateMachine`
(`app/services/agent/state_machine.py`) is the one place any code in this
repository is allowed to mutate `Task.state`.
