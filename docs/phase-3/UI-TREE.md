# UI Tree

## 1. Two layers, deliberately kept separate

- `computer_control.core.models.UIElementNode` — the raw, backend-shaped
  tree (`UIElementInfo` plus `children`/`is_password`), produced by
  `UIAutomationBackend.get_tree()`. Windows-only, real via
  `WindowsUIAutomationBackend.get_tree` (`computer_control/windows/ui_automation.py`),
  fake via `FakeUIAutomationBackend.seed_tree`/`get_tree`
  (`computer_control/testing/fake_backends.py`).
- `vision.core.models.SceneNode` — the normalized, platform-independent
  tree a future AI planner actually consumes, built via
  `SceneNode.from_ui_element_node()`. `control_type` is renamed `role`;
  everything else carries over 1:1. **A raw `UIElementNode` is never
  returned directly from a Phase 3 tool** — `ui.get_tree` always returns
  the normalized `SceneNode` shape (see `PHASE-3-IMPLEMENTATION-PLAN.md`
  §1, "never expose raw UIA structures to future AI agents").

## 2. `get_tree` implementation

`WindowsUIAutomationBackend.get_tree(window_title, max_depth)` walks
`pywinauto`'s descendant tree recursively, bounded by `max_depth` (default
8, tool-configurable up to 32) so a pathological UI tree can't produce an
unbounded walk. A failure on any individual descendant (`element.children()`
raising) is caught and that branch is skipped rather than aborting the
whole walk — a single stale/inaccessible control is common in real UIs.

## 3. Password-field detection

`_is_password_element` checks, in order: the real UIA `is_password`
accessor when the pywinauto element exposes it, then a name/automation-id/
class-name substring fallback (`password`, `passwd`, `secret`, `pwd`).
The result is carried on `UIElementNode.is_password` and propagated
through `SceneNode.is_password` into `GroundedElement.is_password` /
`privacy_level` — see `PRIVACY.md`.

## 4. Verified vs. reviewed-only

`get_tree`'s pywinauto-calling code is real but Windows-only and **not**
runtime-verified in this container (`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md`
§2 applies unchanged). What **is** verified here: `capture_scene_graph`
(`vision/windows/ui_tree.py`) — which drives the `UIAutomationBackend`
Protocol and does the raw→normalized translation — is exercised for real
against `FakeUIAutomationBackend` in
`tests/integration/test_vision_tools_api.py` and
`tests/security/test_phase3_privacy_redaction.py`, proving the
orchestration, normalization, and privacy-classification logic
end-to-end; only the pywinauto call itself is unverified.

## 5. `ui.find_all`

Phase 2 shipped single-element `ui.find`/`ui.click`/`ui.type` but no
"return every match" tool. Phase 3 adds `ui.find_all`, wrapping the
already-existing `UIAutomationBackend.find_all` (Protocol method existed
since Phase 2, just unregistered as a tool).
