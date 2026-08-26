# Windows UI Automation

## Selector engine (`computer_control.core.selectors.UISelector`)

A fixed, typed set of criteria — `automation_id`, `name`, `control_type`,
`class_name`, `text` — ANDed together, with named constructors
(`by_automation_id`, `by_name`, `by_control_type`, `by_class_name`,
`by_text`) matching the brief's §12 list exactly. There is no free-form
query string field anywhere on the model, and construction fails
(`pydantic.ValidationError`) if none of the criteria are set — "at least
one, never zero" is enforced by the type, not a runtime `if` a future
change could remove. `UISelector.matches()` is pure, OS-independent
matching logic against `UIElementInfo`, shared between the fake backend
(for tests) and structurally mirrored by the real Windows backend's own
criteria-building (`selector_to_pywinauto_criteria`).

## `wait_for_element` (`computer_control.core.waiting`)

Polls `backend.find_element()` on a fixed interval (default 250ms) until
found or a timeout (default 5s) elapses, then raises
`UIElementNotFoundError` — never silently returns nothing, never clicks a
different, unrelated element as a fallback. Its only suspension point is
`asyncio.sleep`, so a caller's `task.cancel()` interrupts it immediately
with a real `asyncio.CancelledError` — no bespoke cancellation flag needed
(verified: `tests/unit/test_wait_for_element.py::test_cancellation_interrupts_the_wait_immediately`).
The retry/timeout logic itself is tested against
`computer_control.testing.FakeUIAutomationBackend`'s `appear_after_calls`
mechanism, which simulates an element that isn't present for the first N
lookups (e.g. a dialog still rendering) — a real, deterministic test of
the polling behavior, not a mock that always returns immediately.

## Real backend (`computer_control.windows.ui_automation`)

`WindowsUIAutomationBackend` uses `pywinauto.Desktop(backend="uia")`,
scoping to a specific window via `title_re` when `UISelector.window_title`
is set, and translating criteria to pywinauto's own
`auto_id`/`title`/`control_type`/`class_name` kwargs
(`selector_to_pywinauto_criteria`) — never string-interpolated into
anything resembling a query language. Element info
(`automation_id`/`name`/`control_type`/`class_name`/`enabled`/`visible`/
`bounds`) is read via pywinauto's `element_info` and `rectangle()`. Not
runtime-verified in this environment — see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2.

## Tools

`ui.find` / `ui.wait_for` are SAFE (read-only discovery; `ui.wait_for` is
literally the same implementation as `ui.find`, exposed under a second
name because callers reason about "wait until this appears" differently
from "look for this" even though the code path is identical — documented
in `app/services/computer_control/ui_tools.py` rather than left as an
unexplained duplicate). `ui.click` / `ui.type` are SENSITIVE — same
reasoning as `mouse.click`/`keyboard.type`: a semantic click or typed
input can still trigger arbitrary application behavior.
