"""keyboard.* and mouse.* tools. docs/phase-2/INPUT-CONTROL.md.

Every tool here requires a target (InputTarget for keyboard, UISelector
for mouse) — constructing either with no identifying criteria raises a
pydantic ValidationError, which app.services.computer_control.support
maps to TARGET_CONTEXT_REQUIRED. docs/phase-2 §16: 'If target context is
missing: DO NOT EXECUTE.'

Risk tier: SENSITIVE for every tool here — keyboard/mouse input can
trigger arbitrary application behavior (submit a form, send a message,
navigate away), unlike the read-only or cosmetic-window-state tools
elsewhere in this subpackage.
"""

from __future__ import annotations

from computer_control.core.models import InputTarget
from computer_control.core.results import ActionResult, ActionStatus
from computer_control.core.selectors import UISelector
from pydantic import BaseModel
from veyra_contracts import (
    ConfirmationPolicy,
    ErrorCategory,
    ErrorInfo,
    EvidenceTier,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
)

from app.services.computer_control.backends import BackendBundle
from app.services.computer_control.support import (
    ToolFn,
    callable_executor,
    platform_unsupported_executor,
)


class _TypeArgs(BaseModel):
    target: InputTarget
    text: str


class _PressArgs(BaseModel):
    target: InputTarget
    key: str


class _HotkeyArgs(BaseModel):
    target: InputTarget
    keys: list[str]


class _TypeActiveArgs(BaseModel):
    text: str


class _PressActiveArgs(BaseModel):
    key: str


class _HotkeyActiveArgs(BaseModel):
    keys: list[str]


class _MouseArgs(BaseModel):
    selector: UISelector


class _ScrollArgs(BaseModel):
    selector: UISelector
    amount: int = 3


def _tool(
    tool_id: str,
    category: ToolCategory,
    name: str,
    description: str,
    args_model: type[BaseModel],
):
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=category,
        input_schema=args_model.model_json_schema(),
        output_schema={"type": "object"},
        risk_level=RiskLevel.SENSITIVE,
        required_permission=f"computer_control.{tool_id}",
        confirmation_policy=ConfirmationPolicy.SESSION,
        verification_strategy="none — input delivery is fire-and-forget; "
        "callers should verify the intended effect via a follow-up "
        "ui.find/window state check.",
    )


import sys as _sys

_WINDOWS = _sys.platform == "win32"
_MODIFIER_PREFIXES = {"ctrl": "^", "alt": "%", "shift": "+"}


def _build_key_sequence(keys: list[str]) -> str:
    """Convert e.g. ['ctrl', 'c'] → '^c' for pywinauto send_keys."""
    if not keys:
        raise ValueError("hotkey requires at least one key.")
    *modifiers, key = keys
    prefix = ""
    for mod in modifiers:
        norm = mod.lower()
        if norm not in _MODIFIER_PREFIXES:
            raise ValueError(f"Unknown modifier '{mod}'.")
        prefix += _MODIFIER_PREFIXES[norm]
    return f"{prefix}{{{key.upper()}}}" if len(key) > 1 else f"{prefix}{key}"


def _pywinauto_send_keys(sequence: str, with_spaces: bool = False) -> bool:
    """Type `sequence` into whatever element currently has keyboard focus.
    Returns False when pywinauto is unavailable (non-Windows host)."""
    try:
        import pywinauto.keyboard  # noqa: PLC0415
        pywinauto.keyboard.send_keys(sequence, with_spaces=with_spaces, pause=0.05)
        return True
    except Exception:
        return False


def build_input_tools(bundle: BackendBundle) -> list[tuple[ToolDefinition, object]]:
    keyboard = bundle.keyboard
    mouse = bundle.mouse
    unsupported = keyboard is None or mouse is None

    async def keyboard_type(call: ToolCallRequest) -> ActionResult:
        args = _TypeArgs(**call.arguments)
        ok = await keyboard.type_text(args.target, args.text)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="keyboard.type",
            target=args.target.window_title or args.target.window_handle,
            execution_time_ms=0,
        )

    async def keyboard_press(call: ToolCallRequest) -> ActionResult:
        args = _PressArgs(**call.arguments)
        ok = await keyboard.press(args.target, args.key)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="keyboard.press",
            target=args.target.window_title or args.target.window_handle,
            execution_time_ms=0,
        )

    async def keyboard_hotkey(call: ToolCallRequest) -> ActionResult:
        args = _HotkeyArgs(**call.arguments)
        ok = await keyboard.hotkey(args.target, args.keys)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="keyboard.hotkey",
            target=args.target.window_title or args.target.window_handle,
            execution_time_ms=0,
        )

    def _mouse_action(tool_id: str, method_name: str):
        async def _run(call: ToolCallRequest) -> ActionResult:
            args = _MouseArgs(**call.arguments)
            method = getattr(mouse, method_name)
            ok = await method(args.selector)
            return ActionResult(
                status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
                tool=tool_id,
                target=args.selector.name or args.selector.automation_id,
                execution_time_ms=0,
            )

        return _run

    async def mouse_scroll(call: ToolCallRequest) -> ActionResult:
        args = _ScrollArgs(**call.arguments)
        ok = await mouse.scroll(args.selector, args.amount)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="mouse.scroll",
            target=args.selector.name or args.selector.automation_id,
            execution_time_ms=0,
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "keyboard.type",
                ToolCategory.KEYBOARD,
                "Type Text",
                "Types text into a specific target window/element.",
                _TypeArgs,
            ),
            keyboard_type,
        ),
        (
            _tool(
                "keyboard.press",
                ToolCategory.KEYBOARD,
                "Press Key",
                "Presses a single key in a specific target window/element.",
                _PressArgs,
            ),
            keyboard_press,
        ),
        (
            _tool(
                "keyboard.hotkey",
                ToolCategory.KEYBOARD,
                "Press Hotkey",
                "Presses a modifier key combination in a specific target.",
                _HotkeyArgs,
            ),
            keyboard_hotkey,
        ),
        (
            _tool(
                "mouse.move",
                ToolCategory.MOUSE,
                "Move Mouse",
                "Moves the cursor to a resolved UI element.",
                _MouseArgs,
            ),
            _mouse_action("mouse.move", "move"),
        ),
        (
            _tool(
                "mouse.click",
                ToolCategory.MOUSE,
                "Click",
                "Clicks a resolved UI element.",
                _MouseArgs,
            ),
            _mouse_action("mouse.click", "click"),
        ),
        (
            _tool(
                "mouse.double_click",
                ToolCategory.MOUSE,
                "Double-Click",
                "Double-clicks a resolved UI element.",
                _MouseArgs,
            ),
            _mouse_action("mouse.double_click", "double_click"),
        ),
        (
            _tool(
                "mouse.right_click",
                ToolCategory.MOUSE,
                "Right-Click",
                "Right-clicks a resolved UI element.",
                _MouseArgs,
            ),
            _mouse_action("mouse.right_click", "right_click"),
        ),
        (
            _tool(
                "mouse.scroll",
                ToolCategory.MOUSE,
                "Scroll",
                "Scrolls at a resolved UI element.",
                _ScrollArgs,
            ),
            mouse_scroll,
        ),
    ]

    result: list[tuple[ToolDefinition, object]] = []
    for definition, fn in specs:
        executor = (
            platform_unsupported_executor(definition.id)
            if unsupported
            else callable_executor(
                definition.id, fn, default_evidence_tier=EvidenceTier.UI_AUTOMATION
            )
        )
        result.append((definition, executor))

    # "Active window" variants — type/press/hotkey into whatever element
    # currently has keyboard focus, no window targeting required.
    # Windows-only (pywinauto.keyboard); on other platforms they register
    # as platform_unsupported so the tool registry stays complete and
    # the tool selector can still reference them without KeyError.

    async def _type_active(call: ToolCallRequest) -> ActionResult:
        args = _TypeActiveArgs(**call.arguments)
        ok = _pywinauto_send_keys(args.text, with_spaces=True)
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="keyboard.type_active",
            execution_time_ms=0,
        )

    async def _press_active(call: ToolCallRequest) -> ActionResult:
        args = _PressActiveArgs(**call.arguments)
        key = args.key.strip()
        key_seq = f"{{{key.upper()}}}" if len(key) > 1 else key
        ok = _pywinauto_send_keys(key_seq)
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="keyboard.press_active",
            execution_time_ms=0,
        )

    async def _hotkey_active(call: ToolCallRequest) -> ActionResult:
        args = _HotkeyActiveArgs(**call.arguments)
        try:
            sequence = _build_key_sequence(args.keys)
        except ValueError as exc:
            return ActionResult(
                status=ActionStatus.FAILED,
                tool="keyboard.hotkey_active",
                execution_time_ms=0,
                error=ErrorInfo(
                    code=ErrorCategory.INVALID_ARGUMENTS,
                    message=str(exc),
                    correlation_id="",
                ),
            )
        ok = _pywinauto_send_keys(sequence)
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="keyboard.hotkey_active",
            execution_time_ms=0,
        )

    active_specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "keyboard.type_active",
                ToolCategory.KEYBOARD,
                "Type Text (Active Window)",
                "Types text into the currently focused element without needing a window target.",
                _TypeActiveArgs,
            ),
            _type_active,
        ),
        (
            _tool(
                "keyboard.press_active",
                ToolCategory.KEYBOARD,
                "Press Key (Active Window)",
                "Presses a single key (e.g. ENTER, ESCAPE, TAB, PAGEDOWN) in the focused element.",
                _PressActiveArgs,
            ),
            _press_active,
        ),
        (
            _tool(
                "keyboard.hotkey_active",
                ToolCategory.KEYBOARD,
                "Press Hotkey (Active Window)",
                "Sends a modifier key combination (e.g. Ctrl+C, Ctrl+V, Alt+F4) to the focused element.",
                _HotkeyActiveArgs,
            ),
            _hotkey_active,
        ),
    ]
    for definition, fn in active_specs:
        executor = (
            platform_unsupported_executor(definition.id)
            if not _WINDOWS
            else callable_executor(definition.id, fn, default_evidence_tier=EvidenceTier.UI_AUTOMATION)
        )
        result.append((definition, executor))

    return result
