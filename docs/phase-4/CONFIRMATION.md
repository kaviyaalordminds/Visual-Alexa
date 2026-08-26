# Confirmation

`ConfirmationManager` (`app/services/agent/confirmation.py`). Never
decides *whether* confirmation is required (the Policy Engine alone does
— see `POLICY-INTEGRATION.md`); only builds the human-facing text and two
supporting checks.

## 1. Specific, understandable prompts (brief §21-22)

`build_prompt(step, definition)` composes the tool's display name, the
concrete target (`path`/`application` argument, falling back to the
step's description), the risk tier, and a plain-language reason keyed off
risk level. Never the brief's own bad example ("Allow VEYRA?") — always
names the exact action and target, verified directly
(`tests/unit/test_agent_confirmation.py::test_prompt_is_not_generic`).

## 2. Time-limited (brief §22)

`confirmation_expired(seconds_ago, ttl_seconds)` — a pure predicate. The
actual enforcement is the `PermissionGrant.expires_at` set by
`POST /tasks/{id}/confirm` (300s TTL) — see `POLICY-INTEGRATION.md` §4.

## 3. Confirmation escalation (brief §23)

`plan_changed_materially(original_step, new_step)` compares tool_id and
the same target field the prompt itself displayed — "what the user saw"
is exactly "what would trigger re-confirmation," not the full argument
dict (which could differ in cosmetic ways the user never saw). Not yet
wired into the orchestrator's replan path (replanning itself is a
documented gap — see `PHASE-4-TEST-RESULTS.md`), but the pure comparison
function is implemented and unit-tested now so a future replanning
implementation has it ready.

## 4. Denial

`POST /tasks/{id}/confirm` with `DENY`/`CANCEL` transitions the task
directly to `CANCELLED` (not merely a cooperative-cancellation signal,
since the orchestrator's loop has already stopped and left nothing
running to observe one) — verified end-to-end
(`tests/integration/test_agent_tasks_api.py::test_confirmation_denial_cancels_without_acting`):
the pending filesystem effect never happens.

## 5. Verified end-to-end, not just modeled

`tests/integration/test_agent_tasks_api.py::test_confirmation_pause_and_resume`
drives a real MODERATE `filesystem.create_folder` step through the actual
API: pauses at `WAITING_PERMISSION` with the folder genuinely absent,
confirms, and the folder is genuinely created only after that — proving
the pause was real, not simulated.
