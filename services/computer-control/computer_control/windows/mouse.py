"""Real Windows MouseBackend. NOT executable/testable in this Linux
development environment — see computer_control.windows package docstring
and docs/phase-2/INPUT-CONTROL.md.

Every method resolves a UISelector to a concrete element first; pywinauto
computes the click coordinates internally from that element's bounding
rectangle. There is no raw-coordinate entry point anywhere in this module
— see docs/phase-2 §10 and computer_control.core.backends.MouseBackend.
"""

from __future__ import annotations

from typing import Any

from computer_control.core.selectors import UISelector
from computer_control.windows.ui_automation import selector_to_pywinauto_criteria


def _resolve(selector: UISelector) -> Any:
    import pywinauto

    desktop = pywinauto.Desktop(backend="uia")
    scope = desktop
    if selector.window_title:
        import re

        scope = desktop.window(title_re=f".*{re.escape(selector.window_title)}.*")
    return scope.child_window(**selector_to_pywinauto_criteria(selector))


class WindowsMouseBackend:
    async def move(self, selector: UISelector) -> bool:
        try:
            element = _resolve(selector)
            if not element.exists():
                return False
            rect = element.rectangle()
            import pywinauto

            pywinauto.mouse.move(coords=(rect.mid_point().x, rect.mid_point().y))
            return True
        except Exception:
            return False

    async def click(self, selector: UISelector) -> bool:
        try:
            element = _resolve(selector)
            if not element.exists() or not element.is_enabled():
                return False
            element.click_input()
            return True
        except Exception:
            return False

    async def double_click(self, selector: UISelector) -> bool:
        try:
            element = _resolve(selector)
            if not element.exists() or not element.is_enabled():
                return False
            element.double_click_input()
            return True
        except Exception:
            return False

    async def right_click(self, selector: UISelector) -> bool:
        try:
            element = _resolve(selector)
            if not element.exists() or not element.is_enabled():
                return False
            element.right_click_input()
            return True
        except Exception:
            return False

    async def scroll(self, selector: UISelector, amount: int) -> bool:
        try:
            element = _resolve(selector)
            if not element.exists():
                return False
            element.scroll("down" if amount < 0 else "up", "wheel", amount=abs(amount))
            return True
        except Exception:
            return False
