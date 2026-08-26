"""Visual change detection: computes a `SceneDiff` between two
`SceneGraph`s. docs/phase-3/SCENE-DIFF.md.

Pure Python, no OS dependency — genuinely tested here. Used to build the
ACT -> OBSERVE -> VERIFY loop enhancement to Phase 2's verification
(docs/phase-3 §25/§26): capture a scene before an action, capture again
after, diff the two, and only then decide whether the action's effect is
actually visible on screen.
"""

from __future__ import annotations

from vision.core.models import SceneChange, SceneDiff, SceneGraph, SceneNode


def _identity_key(node: SceneNode) -> str:
    """docs/phase-3 §24 — nodes are matched across the two scenes by
    identity (automation_id when present, else name+role+class_name), not
    by list position, so an unrelated reordering doesn't read as
    added+removed."""
    if node.automation_id:
        return f"id:{node.automation_id}"
    return f"shape:{node.name}|{node.role}|{node.class_name}"


def _index(graph: SceneGraph) -> dict[str, SceneNode]:
    return {_identity_key(node): node for node in graph.root.walk()}


def _node_content_changed(before: SceneNode, after: SceneNode) -> bool:
    return (
        before.name != after.name
        or before.enabled != after.enabled
        or before.visible != after.visible
    )


def _bounds_changed(before: SceneNode, after: SceneNode) -> bool:
    return before.bounds != after.bounds


def compute_scene_diff(before: SceneGraph, after: SceneGraph) -> SceneDiff:
    before_index = _index(before)
    after_index = _index(after)

    added = [node for key, node in after_index.items() if key not in before_index]
    removed = [node for key, node in before_index.items() if key not in after_index]
    changed: list[SceneChange] = []
    moved: list[SceneChange] = []

    for key, before_node in before_index.items():
        after_node = after_index.get(key)
        if after_node is None:
            continue
        if _bounds_changed(before_node, after_node):
            moved.append(
                SceneChange(
                    node=after_node, change_type="moved", previous_bounds=before_node.bounds
                )
            )
        if _node_content_changed(before_node, after_node):
            changed.append(SceneChange(node=after_node, change_type="changed"))

    return SceneDiff(
        added=added,
        removed=removed,
        changed=changed,
        moved=moved,
        before_captured_at=before.captured_at,
        after_captured_at=after.captured_at,
    )
