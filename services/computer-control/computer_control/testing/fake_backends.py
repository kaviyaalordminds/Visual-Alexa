"""In-memory fake backends. Deterministic, no OS calls, safe to run
anywhere. Each one implements the corresponding Protocol in
computer_control.core.backends exactly.
"""

from __future__ import annotations

import itertools

from computer_control.core.models import (
    ApplicationInfo,
    Rect,
    ScreenCaptureResult,
    UIElementInfo,
    UIElementNode,
    WindowInfo,
)
from computer_control.core.selectors import UISelector


class FakeApplicationBackend:
    """Simulates a small set of "installed" applications and the
    processes launched from them, entirely in memory."""

    def __init__(self, known_executables: dict[str, str] | None = None) -> None:
        # name -> executable_path, standing in for what a real
        # ApplicationRegistry resolver would already have validated.
        self._known = known_executables or {}
        self._running: dict[int, ApplicationInfo] = {}
        self._pid_counter = itertools.count(1000)

    async def list_running(self) -> list[ApplicationInfo]:
        return list(self._running.values())

    async def find(self, query: str) -> list[ApplicationInfo]:
        query_lower = query.lower()
        return [app for app in self._running.values() if query_lower in app.name.lower()]

    async def launch(self, executable_path: str, args: list[str]) -> ApplicationInfo:
        name = next(
            (n for n, path in self._known.items() if path == executable_path),
            executable_path,
        )
        pid = next(self._pid_counter)
        app = ApplicationInfo(name=name, process_id=pid, window_title=name, state="running")
        self._running[pid] = app
        return app

    async def focus(self, process_id: int) -> bool:
        return process_id in self._running

    async def is_running(self, process_id: int) -> bool:
        return process_id in self._running

    async def close(self, process_id: int) -> bool:
        return self._running.pop(process_id, None) is not None


class FakeWindowBackend:
    def __init__(self) -> None:
        self._windows: dict[str, WindowInfo] = {}
        self._handle_counter = itertools.count(1)

    def seed_window(self, window: WindowInfo) -> None:
        self._windows[window.handle] = window

    def add_window_for_process(self, process_id: int, title: str) -> WindowInfo:
        handle = f"fake-hwnd-{next(self._handle_counter)}"
        window = WindowInfo(handle=handle, title=title, process_id=process_id)
        self._windows[handle] = window
        return window

    async def list_windows(self) -> list[WindowInfo]:
        return list(self._windows.values())

    async def find_window(self, title_query: str) -> WindowInfo | None:
        query_lower = title_query.lower()
        for window in self._windows.values():
            if query_lower in window.title.lower():
                return window
        return None

    async def get_window(self, handle: str) -> WindowInfo | None:
        return self._windows.get(handle)

    async def focus_window(self, handle: str) -> bool:
        if handle not in self._windows:
            return False
        for h, w in self._windows.items():
            self._windows[h] = w.model_copy(update={"is_active": h == handle})
        return True

    async def minimize(self, handle: str) -> bool:
        window = self._windows.get(handle)
        if window is None:
            return False
        self._windows[handle] = window.model_copy(
            update={"is_minimized": True, "is_maximized": False}
        )
        return True

    async def maximize(self, handle: str) -> bool:
        window = self._windows.get(handle)
        if window is None:
            return False
        self._windows[handle] = window.model_copy(
            update={"is_maximized": True, "is_minimized": False}
        )
        return True

    async def restore(self, handle: str) -> bool:
        window = self._windows.get(handle)
        if window is None:
            return False
        self._windows[handle] = window.model_copy(
            update={"is_maximized": False, "is_minimized": False}
        )
        return True

    async def close_window(self, handle: str) -> bool:
        return self._windows.pop(handle, None) is not None

    async def get_active_window(self) -> WindowInfo | None:
        return next((w for w in self._windows.values() if w.is_active), None)


class FakeUIAutomationBackend:
    """`appear_after_calls` simulates an element that isn't present for
    the first N lookups (e.g. a dialog still rendering) — used to test
    wait_for_element's polling/retry behavior for real, without a UI."""

    def __init__(self) -> None:
        self._elements: list[UIElementInfo] = []
        self._appear_after_calls: dict[str, int] = {}
        self._call_counts: dict[str, int] = {}
        self._tree: UIElementNode | None = None

    def seed_tree(self, tree: UIElementNode) -> None:
        """docs/phase-3/UI-TREE.md testing support — seeds a full
        (possibly nested) tree for `get_tree()` to return, independent of
        `seed_element`'s flat list used by find/find_all/click/type."""
        self._tree = tree

    def seed_element(self, element: UIElementInfo, *, appear_after_calls: int = 0) -> None:
        self._elements.append(element)
        key = element.automation_id or element.name or ""
        if appear_after_calls:
            self._appear_after_calls[key] = appear_after_calls

    def _is_visible_yet(self, element: UIElementInfo) -> bool:
        key = element.automation_id or element.name or ""
        threshold = self._appear_after_calls.get(key, 0)
        if threshold == 0:
            return True
        self._call_counts[key] = self._call_counts.get(key, 0) + 1
        return self._call_counts[key] > threshold

    async def find_element(
        self, selector: UISelector, timeout_seconds: float
    ) -> UIElementInfo | None:
        for element in self._elements:
            if selector.matches(element) and self._is_visible_yet(element):
                return element
        return None

    async def find_all(self, selector: UISelector) -> list[UIElementInfo]:
        return [e for e in self._elements if selector.matches(e)]

    async def click_element(self, selector: UISelector, timeout_seconds: float) -> bool:
        element = await self.find_element(selector, timeout_seconds)
        return element is not None and element.enabled

    async def type_into_element(
        self, selector: UISelector, text: str, timeout_seconds: float
    ) -> bool:
        element = await self.find_element(selector, timeout_seconds)
        return element is not None and element.enabled

    async def get_tree(
        self, window_title: str | None = None, max_depth: int = 8
    ) -> UIElementNode:
        if self._tree is not None:
            return self._tree
        # No tree seeded: synthesize a flat one-level tree from whatever
        # elements were seeded via seed_element, so tests that only need
        # "some tree came back" don't have to seed both.
        return UIElementNode(
            automation_id=None,
            name=window_title or "Desktop",
            control_type="Window",
            children=[UIElementNode(**e.model_dump()) for e in self._elements],
        )


class FakeScreenBackend:
    """Deterministic screen capture double — a real `MssScreenBackend`
    already works in this environment (verified against Xvfb), so this
    fake exists only for tests that want to assert capture_region's
    call shape without a real display."""

    def __init__(self) -> None:
        self.capture_region_calls: list[Rect] = []

    async def capture_full(self) -> ScreenCaptureResult:
        return ScreenCaptureResult(image_base64="", width=1920, height=1080, display_index=1)

    async def capture_window(self, handle: str) -> ScreenCaptureResult:
        return ScreenCaptureResult(
            image_base64="", width=800, height=600, window_handle=handle
        )

    async def capture_active_window(self) -> ScreenCaptureResult:
        return ScreenCaptureResult(image_base64="", width=800, height=600)

    async def capture_region(self, bounds: Rect, display_index: int = 1) -> ScreenCaptureResult:
        self.capture_region_calls.append(bounds)
        return ScreenCaptureResult(
            image_base64="",
            width=bounds.width,
            height=bounds.height,
            display_index=display_index,
        )
