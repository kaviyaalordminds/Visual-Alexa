"""UI tree capture + normalization. docs/phase-3/UI-TREE.md.

`capture_scene_graph` itself has no OS-specific import — it drives the
`UIAutomationBackend.get_tree` Protocol method (real on Windows via
`computer_control.windows.ui_automation.WindowsUIAutomationBackend`, fake
everywhere else via `computer_control.testing.FakeUIAutomationBackend`),
so it is genuinely exercised in this environment against the fake backend
even though the real backend it drives in production is Windows-only. It
lives under `vision.windows` because on a real host it only produces
non-trivial data on Windows — matching
docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §1/§3.
"""

from __future__ import annotations

from computer_control.core.backends import UIAutomationBackend

from vision.core.models import SceneGraph, SceneNode


async def capture_scene_graph(
    backend: UIAutomationBackend,
    *,
    window_title: str | None = None,
    window_handle: str | None = None,
    max_depth: int = 8,
    task_id: str | None = None,
    correlation_id: str | None = None,
) -> SceneGraph:
    raw_tree = await backend.get_tree(window_title=window_title, max_depth=max_depth)
    return SceneGraph(
        root=SceneNode.from_ui_element_node(raw_tree),
        window_handle=window_handle,
        window_title=window_title,
        task_id=task_id,
        correlation_id=correlation_id,
    )
