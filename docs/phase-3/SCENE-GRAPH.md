# Scene Graph

`vision.core.models.SceneNode` / `SceneGraph` (`vision/core/models.py`) —
the platform-independent, normalized UI tree. Fields: `id` (generated),
`automation_id`, `name`, `role` (renamed from `control_type`),
`class_name`, `enabled`, `visible`, `bounds`, `is_password`,
`supported_patterns`, `children`. `SceneNode.walk()` depth-first-flattens
a tree into a list, used by fusion/grounding/diff so those modules reason
over flat candidate lists without re-implementing recursion.

`SceneGraph` wraps one root `SceneNode` plus provenance
(`window_handle`, `window_title`, `captured_at`, `task_id`,
`correlation_id`, `source: ContentSource = UI_OBSERVATION`).

Built via `SceneNode.from_ui_element_node(UIElementNode)` — see
`UI-TREE.md` for why the raw and normalized shapes are kept as two
distinct types. Fully tested (`tests/unit/test_vision_scene_node.py`):
flat and nested normalization, `walk()` ordering, and `is_password`
propagation, all pure Python with no OS dependency.
