# Confirmation (Phase 11 — unchanged, re-verified)

`ConfirmationManager` (`app/services/agent/confirmation.py`) and the
Policy Engine's confirmation gate are unchanged by Phase 11 — the full
contract remains `docs/phase-4/CONFIRMATION.md` and
`docs/security/08-SENSITIVE-ACTION-POLICY.md`. This page records what was
re-verified against this phase's three additions.

## Who decides *whether* confirmation is required — unchanged

`ConfirmationManager` never decides *whether* a step needs confirmation —
that is the Policy Engine's job alone, unconditionally, for every step:

- `RiskLevel.SAFE` — always allowed, no confirmation.
- `RiskLevel.CRITICAL` — never satisfiable by any stored grant, including
  `ALWAYS_ALLOW` — fresh, explicit confirmation every time.
- `RiskLevel.MODERATE`/`SENSITIVE` — a matching, unexpired
  `PermissionGrant`, or a confirmation prompt.

`ConfirmationManager.build_prompt` only turns a `PolicyDecision(requires_
confirmation=True)` plus the triggering step into the exact,
non-paraphrased prompt text the security spec requires — unchanged.

## How Phase 11's additions interact with this gate

- **Real `REPLAN`**: a replanned step is a normal `PlanStep` with its own
  `risk_level`, evaluated by the Policy Engine exactly like a first-attempt
  step. If a replanned plan happens to include a step requiring
  confirmation, `_execute_plan`'s existing `PERMISSION_DENIED` +
  `user_action_required` handling pauses at `WAITING_PERMISSION` and
  builds a prompt exactly as it always has — no new code path.
- **`WorkflowMemory` alias resolution**: resolves to a `filesystem.open`
  step, `RiskLevel.SAFE` (unchanged from the search-based path) — no
  confirmation involved, same as the existing `open_file` template.
- **`browser_task` planning**: all three tools it plans
  (`browser.launch`/`browser.search`/`browser.get_page`) are
  `RiskLevel.SAFE`, so `_build_plan` computes `requires_confirmation =
  False` for these plans — matching every other SAFE-only template
  (`open_application`, `search_files`). A future browser_task template
  that included a `MODERATE`/`SENSITIVE` browser tool (e.g.
  `browser.upload_file`, which is already `RiskLevel.SENSITIVE` +
  `ConfirmationPolicy.ALWAYS` in Phase 8) would go through this exact same
  gate — nothing in Phase 11 special-cases browser steps.

## `plan_changed_materially` — still not wired into replanning

`ConfirmationManager.plan_changed_materially` (confirmation escalation —
if the concrete target changed after the user approved a step, the
approval no longer covers it) remains implemented and unit-tested but not
wired into the replan path, exactly as `docs/phase-4/PHASE-4-TEST-
RESULTS.md` §6 already documented as technical debt. Phase 11's real
`REPLAN` recovery happens *after* a step failed during execution (not
after a confirmation was granted for a step that then changed) — it does
not create the specific scenario `plan_changed_materially` guards against,
so this remains a documented, pre-existing gap, not a new one Phase 11
introduced or was required to close.

## Verified

`tests/integration/test_agent_tasks_api.py::test_confirmation_pause_and_
resume` and `::test_confirmation_denial_cancels_without_acting` — both
re-ran unmodified (aside from their `fake_plan` test doubles' signature
gaining the new `memory_lookup` keyword) and still pass, proving Phase
11's changes didn't alter confirmation behavior for existing plan shapes.
