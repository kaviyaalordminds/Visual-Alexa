"""docs/phase-3/SCENE-GRAPH.md — SceneNode.from_ui_element_node
normalization: never expose raw UIElementNode structures to a future AI
agent, always translate into the platform-independent SceneNode shape."""

from __future__ import annotations

from computer_control.core.models import Rect, UIElementNode
from vision.core.models import SceneNode


def test_flat_node_normalizes():
    raw = UIElementNode(
        automation_id="save_btn",
        name="Save",
        control_type="Button",
        class_name="Win32Button",
        bounds=Rect(left=1, top=2, width=3, height=4),
        is_password=False,
    )
    node = SceneNode.from_ui_element_node(raw)
    assert node.automation_id == "save_btn"
    assert node.role == "Button"  # control_type -> role rename
    assert node.children == []


def test_nested_tree_normalizes_recursively():
    raw = UIElementNode(
        name="Dialog",
        control_type="Pane",
        children=[
            UIElementNode(name="OK", control_type="Button"),
            UIElementNode(name="Cancel", control_type="Button"),
        ],
    )
    node = SceneNode.from_ui_element_node(raw)
    assert len(node.children) == 2
    assert [c.name for c in node.children] == ["OK", "Cancel"]


def test_walk_flattens_depth_first():
    raw = UIElementNode(
        name="root",
        control_type="Window",
        children=[UIElementNode(name="child", control_type="Text")],
    )
    node = SceneNode.from_ui_element_node(raw)
    flat = node.walk()
    assert [n.name for n in flat] == ["root", "child"]


def test_password_flag_carried_through():
    raw = UIElementNode(name=None, control_type="Edit", is_password=True)
    node = SceneNode.from_ui_element_node(raw)
    assert node.is_password is True
