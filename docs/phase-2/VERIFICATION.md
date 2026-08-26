# Verification Strategy

## "Never return success when verification failed" is structural

`computer_control.core.results.ActionResult` has a `model_validator` that
rejects construction of `status=VERIFIED` unless a `VerificationOutcome`
with `passed=True` is also supplied
(`tests/unit/test_action_result.py::test_verified_requires_a_passing_verification_outcome`).
It is not possible for a tool executor to accidentally report `VERIFIED`
from a launch call that merely didn't raise an exception — the type
itself refuses.

## `ActionStatus` vs. the outer `ToolResultStatus`

`ActionResult.status` (`EXECUTED`/`VERIFIED`/`FAILED`/`PARTIAL`/`TIMEOUT`/
`CANCELLED`/`DENIED`/`UNKNOWN`, per brief §22) is the domain-rich internal
result; it is embedded, serialized, as the `output` field of Phase 1's
`veyra_contracts.ToolResult` (`SUCCESS`/`FAILURE`/`TIMEOUT`/`CANCELLED`),
which remains the contract the Policy Engine/audit/event pipeline already
understands. `app/services/computer_control/support.py`'s `_STATUS_MAP`
is the one place this mapping happens (`EXECUTED`/`VERIFIED` → `SUCCESS`;
`FAILED`/`PARTIAL`/`DENIED`/`UNKNOWN` → `FAILURE`; `TIMEOUT` → `TIMEOUT`;
`CANCELLED` → `CANCELLED`) — chosen deliberately over adding a second,
parallel enum to Phase 1's contracts, since Phase 1's outer contract
already covers the cases the rest of the system (audit log, API response)
needs to distinguish.

## Per-capability verification methods

| Tool family | Verification method | What it actually checks |
|---|---|---|
| `application.launch` / `application.close` | `process_detection` | `ApplicationBackend.is_running(pid)` re-queried after the action |
| `window.focus`/`minimize`/`maximize`/`close` | `window_state_detection` | The relevant `WindowInfo` flag (or absence, for close) re-read after the action |
| `filesystem.create_folder`/`create_file`/`copy`/`move`/`rename` | `filesystem_state_detection` | `Path.stat()` on the resulting path — it genuinely exists, is the right type |
| `filesystem.open` | none (explicit) | No cross-application signal exists to check; reports `EXECUTED`, not `VERIFIED`, and says why in `VerificationOutcome.detail` |
| `filesystem.search`/`list_directory`/`get_metadata` | none | Read-only; there's no postcondition beyond the read itself succeeding |
| `keyboard.*`/`mouse.*` | none (documented) | Fire-and-forget by nature; `ToolDefinition.verification_strategy` explicitly tells callers to follow up with `ui.find`/a window-state check |
| `screen.capture*` | none | A returned image is its own evidence |
| `ui.click`/`ui.type` | `post_action_element_state_check` (declared; not independently re-verified in Phase 2) | Reports `EXECUTED` on a truthy backend call; a genuine independent re-check (e.g. re-reading the element's `Value` pattern after typing) is future work — documented as a known limitation, not silently assumed done |

## Why this matters (the differentiator this whole phase serves)

`docs/research/03-COMPETITOR-WEAKNESSES.md` item 2 — direct action without
reliable verification — was one of the highest-confidence gaps identified
in Phase 1's landscape research: competitor computer-use loops largely
verify by "take another screenshot and let the same model re-interpret
it," which is weaker evidence than an independent, typed postcondition
check. Every verified tool in this phase checks a real, independent signal
(a process existing, a window flag, a file on disk) rather than
re-interpreting its own action.
