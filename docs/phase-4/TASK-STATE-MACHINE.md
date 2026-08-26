# Task State Machine

## 1. Reused, extended, never replaced

`veyra_contracts.enums.TaskState` and `veyra_contracts.tasks.is_legal_transition`
(Phase 1) are reused directly. `TaskStateMachine`
(`app/services/agent/state_machine.py`) is a thin, mandatory wrapper: every
mutation of `Task.state` anywhere in the orchestrator goes through
`TaskStateMachine.transition`, which raises `IllegalTaskTransitionError`
on anything not in the table — brief §8's "never allow arbitrary state
transitions" is structural, verified directly by three real bugs this
discipline caught during Phase 4's own end-to-end testing (see §3).

## 2. Brief-name mapping

The brief's state list maps onto Phase 1's existing names rather than
introducing synonyms:

| Brief name | This codebase |
|---|---|
| `CREATED` | `RECEIVED` |
| `AWAITING_CONFIRMATION` | `WAITING_PERMISSION` |
| `WAITING_FOR_USER` | `WAITING_USER` |
| `VALIDATING` | *(no separate state — see below)* |
| everything else | identical |

No `VALIDATING` state: `TaskPlanner.create_plan` validates the plan
(tool existence, schema, risk) before ever returning it — an invalid plan
never reaches a persisted state at all (`ErrorCategory.INVALID_PLAN`,
handled inline during `PLANNING`), so a `VALIDATING` state would record a
transition with no observable failure edge of its own.

## 3. Additive transitions (all found necessary during real testing, not
speculative)

| Edge | Why |
|---|---|
| `PLANNING → WAITING_USER` | Ambiguity discovered while *building* a plan (e.g. multiple candidate files), not only during `UNDERSTANDING` |
| `EXECUTING → WAITING_PERMISSION` | A later step in a multi-step plan can require confirmation, not only the first |
| `EXECUTING → WAITING_USER` | Human-in-the-loop pause (CAPTCHA/2FA/unexpected prompt) |
| `EXECUTING → RECOVERING` | Matches the brief's own §8 diagram directly |
| `EXECUTING → FAILED` | A hallucinated/unregistered tool is rejected immediately — nothing was attempted, so there's nothing to diagnose in `RECOVERING` first |
| `WAITING_PERMISSION → EXECUTING` / `WAITING_USER → EXECUTING` | Resuming after confirmation or human intervention continues the *same* plan, never forces a full replan |
| `RECOVERING → EXECUTING` | `RETRY`/`REGROUND`/`REOBSERVE` re-attempt the same step directly |
| `* → TIMED_OUT` | Budget exhaustion, from every state where a budget check can fire, distinct from `FAILED` |

Three of these (`EXECUTING → RECOVERING`, `EXECUTING → FAILED`, and the
`WAITING_PERMISSION`-resume-after-confirmation-needing-`_wait_for_terminal`-poll-fix
in test tooling) were discovered as real `IllegalTaskTransitionError`
crashes while running genuine end-to-end tasks through the real API during
this phase's own verification — see `PHASE-4-TEST-RESULTS.md` §3 — proof
the guard is doing real work, not merely modeled.

## 4. `TIMED_OUT` vs. `FAILED`

`TIMED_OUT` (new terminal state) is reached only via `LoopBudgetTracker`
detecting max_steps/timeout/max_replans/loop-detection. `FAILED` is
reached for every other terminal failure (tool error, invalid plan,
unsafe request, capability unavailable, exhausted recovery). A caller can
distinguish "ran out of budget" from "a specific thing went wrong"
without parsing `failure_reason` text.

## 5. Verified

`tests/unit/test_task_transitions.py` (Phase 1's suite, extended with a
`test_budget_exhaustion_reaches_timed_out_from_every_active_state` case
and an updated terminal-states list) plus every real state transition
exercised end-to-end in `tests/integration/test_agent_tasks_api.py` and
`tests/security/test_agent_adversarial.py`.
