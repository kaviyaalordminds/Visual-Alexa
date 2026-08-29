# Permissions

The authoritative permission-tier and grant-storage design is
`02-PERMISSION-MODEL.md`; CRITICAL-tier handling specifically is
`08-SENSITIVE-ACTION-POLICY.md`. This document is the short, task-
execution-facing summary Phase 13 asked for, plus a real worked example.

## The four tiers

| `RiskLevel` | Default behavior |
|---|---|
| `SAFE` | Always allowed — no grant needed, no confirmation. |
| `MODERATE` | Needs a permission grant. With none stored, pauses at `WAITING_PERMISSION` for a fresh confirmation. `ALLOW_ONCE` authorizes exactly one subsequent match and is then revoked; `ALLOW_SESSION`/`ALWAYS_ALLOW` remain valid for later calls until their TTL expires. |
| `SENSITIVE` | Same grant mechanics as `MODERATE`, reserved for higher-impact actions (e.g. sending a message, controlling a device). |
| `CRITICAL` | **Never** satisfied by a stored grant, including `ALWAYS_ALLOW` — always requires fresh, explicit confirmation, every time (`CLAUDE.md`, `08-SENSITIVE-ACTION-POLICY.md`). |

Enforcement is `PolicyEngine`, checked unconditionally inside
`execute_tool_call` (`app/services/tool_execution.py`) for every tool
call — there is no code path that reaches a tool's executor without
this check, including step retries (see `docs/architecture/runtime.md`
on why an idempotent replay of a *successful* call is not a second,
unchecked execution: the check already happened on the original call).

## Confirmation is specific, not vague

When a step pauses at `WAITING_PERMISSION`, `ConfirmationManager.
build_prompt` builds a real, specific prompt bound to the exact tool,
target, and risk level — `"{tool} — {target}. Risk: {level}. {reason}
Continue?"`, never a bare "Allow?" (`docs/phase-4/CONFIRMATION.md`). This
is carried on `Task.result.confirmation_prompt` and is exactly what
`apps/desktop/src/tasks/TaskPanel.tsx` renders with its Allow/Deny
controls (Phase 13 P0-5 — previously nothing in the frontend rendered
this at all, `docs/phase-13-audit.md §8`).

`POST /tasks/{id}/confirm` accepts a `PermissionDecision`
(`ALLOW_ONCE`/`ALLOW_SESSION`/`ALWAYS_ALLOW`/`DENY`/`CANCEL`), creates
the corresponding grant (never for `CRITICAL`), and resumes the same
remaining plan — never a replan. A `DENY` cancels the task without
executing the step.

## Worked example: `filesystem.create_folder`

`filesystem.create_folder` is `MODERATE` (a real write to disk, unlike
`filesystem.search`/`.open`, which are `SAFE`). A task created from
"Create a folder called VEYRA-Test" with no pre-existing grant pauses at
`WAITING_PERMISSION` on its first run — real security, not skipped —
and only creates the folder once `/confirm` with `ALLOW_ONCE` (or a
session/always grant) is called. See
`tests/integration/test_agent_tasks_api.py::
test_create_folder_completes_for_real` for the full real flow, and
`tests/integration/test_agent_tasks_api.py::
test_confirmation_pause_and_resume` for the same mechanics proven
independently of the planner.

## `ALLOW_ONCE` is genuinely single-use

Found and fixed during Phase 13 live verification: `PolicyEngine.
evaluate` (`app/services/policy_engine.py`) now revokes an `ALLOW_ONCE`
grant the moment it satisfies a check, rather than leaving it valid for
its full TTL like `ALLOW_SESSION`. Before this fix, an `ALLOW_ONCE`
decision silently behaved identically to `ALLOW_SESSION` for the whole
5-minute grant window — a real gap between the documented intent
(`confirmation_actions.py`: "single-use... never a standing
ALWAYS_ALLOW") and the actual code. See
`tests/unit/test_policy_engine.py::
test_allow_once_grant_is_consumed_after_a_single_match`.

## What this never does

- No tool executor may be reached by unvalidated or model-originated
  input without this check (`CLAUDE.md` — "never give the LLM
  unrestricted system access").
- No `ALWAYS_ALLOW` grant, however recently created, satisfies a
  `CRITICAL` check.
- A confirmation is bound to the exact task/step/tool/arguments/risk it
  was issued for — it does not carry forward to a different step or a
  replanned attempt.
