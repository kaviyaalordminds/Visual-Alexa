# Scene Diff

`vision.core.diff.compute_scene_diff(before: SceneGraph, after: SceneGraph) -> SceneDiff`
(`vision/core/diff.py`). Pure Python, no OS dependency, genuinely tested.

## 1. Identity, not position

Nodes are matched across the two scenes by identity — `automation_id`
when present, else a `name|role|class_name` shape key — never by list
index, so an unrelated reorder doesn't read as added+removed.

## 2. Categories

- `added` / `removed`: present in one scene's index but not the other's.
- `changed`: same identity, but `name`/`enabled`/`visible` differ.
- `moved`: same identity, but `bounds` differ — carries
  `previous_bounds` so a caller can see both the old and new position.

`SceneDiff.has_changes` is `True` iff any of the four lists is non-empty —
the one predicate `wait_until_scene_changes` (`WAITING`, see below) polls.

## 3. Tool: `scene.diff`

SAFE, no gate at all — it is pure computation over two caller-supplied
`SceneGraph` payloads (typically two `ui.get_tree` results, taken before
and after a Phase 2 action). This keeps the ACT → OBSERVE → VERIFY loop
compositional: capture, act (via Phase 2), capture again, diff — rather
than `scene.diff` needing its own backend access.

## 4. Verified

`tests/unit/test_vision_diff.py` — added/removed/moved/changed/unchanged,
5 tests, pure Python.
