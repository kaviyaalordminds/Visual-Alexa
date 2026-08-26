"""Real Windows WindowBackend, built on pywinauto's UIA backend + pywin32
for foreground-window detection. NOT executable/testable in this Linux
development environment — see computer_control.windows package docstring
and docs/phase-2/WINDOW-CONTROL.md.
"""

from __future__ import annotations

from typing import Any

from computer_control.core.models import Rect, WindowInfo


def _window_to_info(window: Any, is_active: bool = False) -> WindowInfo:
    rect = window.rectangle()
    return WindowInfo(
        handle=str(window.handle),
        title=window.window_text(),
        process_id=window.process_id(),
        is_active=is_active,
        is_minimized=bool(window.is_minimized()),
        is_maximized=bool(window.is_maximized()),
        bounds=Rect(
            left=rect.left, top=rect.top, width=rect.width(), height=rect.height()
        ),
    )


class WindowsWindowBackend:
    def _desktop(self) -> Any:
        import pywinauto

        return pywinauto.Desktop(backend="uia")

    async def list_windows(self) -> list[WindowInfo]:
        return [_window_to_info(w) for w in self._desktop().windows()]

    async def find_window(self, title_query: str) -> WindowInfo | None:
        query_lower = title_query.lower()
        for window in self._desktop().windows():
            if query_lower in window.window_text().lower():
                return _window_to_info(window)
        return None

    async def get_window(self, handle: str) -> WindowInfo | None:
        for window in self._desktop().windows():
            if str(window.handle) == handle:
                return _window_to_info(window)
        return None

    async def focus_window(self, handle: str) -> bool:
        for window in self._desktop().windows():
            if str(window.handle) == handle:
                window.set_focus()
                return True
        return False

    async def minimize(self, handle: str) -> bool:
        for window in self._desktop().windows():
            if str(window.handle) == handle:
                window.minimize()
                return True
        return False

    async def maximize(self, handle: str) -> bool:
        for window in self._desktop().windows():
            if str(window.handle) == handle:
                window.maximize()
                return True
        return False

    async def restore(self, handle: str) -> bool:
        for window in self._desktop().windows():
            if str(window.handle) == handle:
                window.restore()
                return True
        return False

    async def close_window(self, handle: str) -> bool:
        for window in self._desktop().windows():
            if str(window.handle) == handle:
                window.close()
                return True
        return False

    async def get_active_window(self) -> WindowInfo | None:
        import win32gui

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        try:
            window = self._desktop().window(handle=hwnd)
            return _window_to_info(window, is_active=True)
        except Exception:
            return None
