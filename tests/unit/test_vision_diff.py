"""docs/phase-3/SCENE-DIFF.md"""

from __future__ import annotations

from computer_control.core.models import Rect
from vision.core.diff import compute_scene_diff
from vision.core.models import SceneGraph, SceneNode


def _graph(children: list[SceneNode]) -> SceneGraph:
    return SceneGraph(root=SceneNode(name="root", role="Window", children=children))


def test_added_node_detected():
    before = _graph([SceneNode(name="Save", role="Button", automation_id="save")])
    after = _graph(
        [
            SceneNode(name="Save", role="Button", automation_id="save"),
            SceneNode(name="Saved!", role="Text", automation_id="toast"),
        ]
    )
    diff = compute_scene_diff(before, after)
    assert [n.automation_id for n in diff.added] == ["toast"]
    assert diff.removed == []
    assert diff.has_changes is True


def test_removed_node_detected():
    before = _graph(
        [
            SceneNode(name="Save", role="Button", automation_id="save"),
            SceneNode(name="Dialog", role="Pane", automation_id="dlg"),
        ]
    )
    after = _graph([SceneNode(name="Save", role="Button", automation_id="save")])
    diff = compute_scene_diff(before, after)
    assert [n.automation_id for n in diff.removed] == ["dlg"]


def test_moved_node_detected_by_bounds_change():
    before_bounds = Rect(left=0, top=0, width=10, height=10)
    after_bounds = Rect(left=50, top=0, width=10, height=10)
    before = _graph(
        [SceneNode(name="Save", role="Button", automation_id="save", bounds=before_bounds)]
    )
    after = _graph(
        [SceneNode(name="Save", role="Button", automation_id="save", bounds=after_bounds)]
    )
    diff = compute_scene_diff(before, after)
    assert len(diff.moved) == 1
    assert diff.moved[0].previous_bounds.left == 0


def test_unchanged_scene_has_no_changes():
    before = _graph([SceneNode(name="Save", role="Button", automation_id="save")])
    after = _graph([SceneNode(name="Save", role="Button", automation_id="save")])
    diff = compute_scene_diff(before, after)
    assert diff.has_changes is False


def test_content_change_detected_without_bounds_change():
    before = _graph([SceneNode(name="Save", role="Button", automation_id="save", enabled=False)])
    after = _graph([SceneNode(name="Save", role="Button", automation_id="save", enabled=True)])
    diff = compute_scene_diff(before, after)
    assert len(diff.changed) == 1
