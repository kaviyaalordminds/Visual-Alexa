"""Real Windows KeyboardBackend. NOT executable/testable in this Linux
development environment — see computer_control.windows package docstring
and docs/phase-2/INPUT-CONTROL.md.

Every method requires a resolved InputTarget (window handle or title, or
a specific element within it) and focuses that target before sending
input — there is no "type into whatever currently has focus" path. See
docs/phase-2 §9, §16.
"""

from __future__ import annotations

import re
from typing import Any

from computer_control.core.models import InputTarget

_MODIFIER_PREFIXES = {"ctrl": "^", "alt": "%", "shift": "+"}


class InputTargetRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("InputTarget requires window_handle or window_title.")


def _resolve_window(target: InputTarget) -> Any:
    import pywinauto

    desktop = pywinauto.Desktop(backend="uia")
    if target.window_handle:
        return desktop.window(handle=int(target.window_handle))
    if target.window_title:
        return desktop.window(title_re=f".*{re.escape(target.window_title)}.*")
    raise InputTargetRequiredError()


def _resolve_control(target: InputTarget) -> Any:
    window = _resolve_window(target)
    if target.element_automation_id:
        return window.child_window(auto_id=target.element_automation_id)
    return window


def _to_pywinauto_key_sequence(keys: list[str]) -> str:
    """Converts e.g. ["ctrl", "s"] into pywinauto's "^s" hotkey syntax.
    The last entry is the "real" key; every entry before it must be a
    known modifier — anything else raises rather than guessing."""
    if not keys:
        raise ValueError("hotkey() requires at least one key.")
    *modifiers, key = keys
    prefix = ""
    for modifier in modifiers:
        normalized = modifier.lower()
        if normalized not in _MODIFIER_PREFIXES:
            raise ValueError(f"Unknown modifier key '{modifier}'.")
        prefix += _MODIFIER_PREFIXES[normalized]
    return f"{prefix}{{{key.upper()}}}" if len(key) > 1 else f"{prefix}{key}"


class WindowsKeyboardBackend:
    async def type_text(self, target: InputTarget, text: str) -> bool:
        try:
            control = _resolve_control(target)
            control.set_focus()
            control.type_keys(text, with_spaces=True)
            return True
        except Exception:
            return False

    async def press(self, target: InputTarget, key: str) -> bool:
        try:
            control = _resolve_control(target)
            control.set_focus()
            key_code = f"{{{key.upper()}}}" if len(key) > 1 else key
            control.type_keys(key_code)
            return True
        except Exception:
            return False

    async def hotkey(self, target: InputTarget, keys: list[str]) -> bool:
        try:
            control = _resolve_control(target)
            control.set_focus()
            control.type_keys(_to_pywinauto_key_sequence(keys))
            return True
        except Exception:
            return False
