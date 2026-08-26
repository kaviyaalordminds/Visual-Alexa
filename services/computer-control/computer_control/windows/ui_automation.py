"""Real Windows UIAutomationBackend, built on pywinauto's UIA backend. NOT
executable/testable in this Linux development environment — see
computer_control.windows package docstring and
docs/phase-2/WINDOWS-UI-AUTOMATION.md.

Selectors map directly onto pywinauto's own criteria kwargs
(auto_id/title/control_type/class_name) — there is no free-form query
string accepted anywhere in this module, matching docs/phase-2 §12's "do
not allow arbitrary XPath-like unsafe execution."
"""

from __future__ import annotations

import re
from typing import Any

from computer_control.core.models import Rect, UIElementInfo
from computer_control.core.selectors import UISelector


def selector_to_pywinauto_criteria(selector: UISelector) -> dict[str, str]:
    criteria: dict[str, str] = {}
    if selector.automation_id:
        criteria["auto_id"] = selector.automation_id
    if selector.control_type:
        criteria["control_type"] = selector.control_type
    if selector.class_name:
        criteria["class_name"] = selector.class_name
    # `name`/`text` both resolve to pywinauto's `title` criterion — see
    # the identical rationale in computer_control.core.selectors.UISelector.matches.
    if selector.name:
        criteria["title"] = selector.name
    elif selector.text:
        criteria["title"] = selector.text
    return criteria


def _element_to_info(element: Any) -> UIElementInfo:
    info = element.element_info
    rect = element.rectangle()
    return UIElementInfo(
        automation_id=getattr(info, "automation_id", None) or None,
        name=getattr(info, "name", None) or None,
        control_type=getattr(info, "control_type", None) or None,
        class_name=getattr(info, "class_name", None) or None,
        enabled=bool(element.is_enabled()),
        visible=bool(element.is_visible()),
        bounds=Rect(left=rect.left, top=rect.top, width=rect.width(), height=rect.height()),
    )


class WindowsUIAutomationBackend:
    def _scope(self, selector: UISelector) -> Any:
        import pywinauto

        desktop = pywinauto.Desktop(backend="uia")
        if selector.window_title:
            return desktop.window(title_re=f".*{re.escape(selector.window_title)}.*")
        return desktop

    async def find_element(
        self, selector: UISelector, timeout_seconds: float
    ) -> UIElementInfo | None:
        try:
            child = self._scope(selector).child_window(**selector_to_pywinauto_criteria(selector))
            if not child.exists(timeout=timeout_seconds):
                return None
            return _element_to_info(child)
        except Exception:
            return None

    async def find_all(self, selector: UISelector) -> list[UIElementInfo]:
        try:
            matches = self._scope(selector).children(**selector_to_pywinauto_criteria(selector))
            return [_element_to_info(m) for m in matches]
        except Exception:
            return []

    async def click_element(self, selector: UISelector, timeout_seconds: float) -> bool:
        try:
            child = self._scope(selector).child_window(**selector_to_pywinauto_criteria(selector))
            if not child.exists(timeout=timeout_seconds) or not child.is_enabled():
                return False
            child.click_input()
            return True
        except Exception:
            return False

    async def type_into_element(
        self, selector: UISelector, text: str, timeout_seconds: float
    ) -> bool:
        try:
            child = self._scope(selector).child_window(**selector_to_pywinauto_criteria(selector))
            if not child.exists(timeout=timeout_seconds) or not child.is_enabled():
                return False
            child.set_focus()
            child.type_keys(text, with_spaces=True)
            return True
        except Exception:
            return False
