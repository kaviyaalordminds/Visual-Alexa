"""window.* tools. docs/phase-2/WINDOW-CONTROL.md.

Risk tiers: list/find/get_active/get_bounds/get_title/focus/minimize/
maximize/restore are SAFE (cosmetic, fully reversible — matches the
product brief's own 'open application' SAFE example); close is MODERATE,
same reasoning as application.close.
"""

from __future__ import annotations

from computer_control.core.results import ActionResult, ActionStatus, VerificationOutcome
from pydantic import BaseModel
from veyra_contracts import (
    ConfirmationPolicy,
    ErrorCategory,
    EvidenceTier,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
)

from app.services.computer_control.backends import BackendBundle
from app.services.computer_control.support import (
    ToolFn,
    ToolLogicError,
    callable_executor,
    platform_unsupported_executor,
)


class _EmptyArgs(BaseModel):
    pass


class _TitleQueryArgs(BaseModel):
    title_query: str


class _HandleArgs(BaseModel):
    handle: str


class _ControlByTitleArgs(BaseModel):
    title_query: str
    action: str = "focus"


def _tool(tool_id: str, name: str, description: str, args_model: type[BaseModel], risk: RiskLevel):
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=ToolCategory.WINDOWS,
        input_schema=args_model.model_json_schema(),
        output_schema={"type": "object"},
        risk_level=risk,
        required_permission=f"computer_control.{tool_id}",
        confirmation_policy=(
            ConfirmationPolicy.NEVER if risk == RiskLevel.SAFE else ConfirmationPolicy.SESSION
        ),
        verification_strategy="window_state_detection",
    )


def build_window_tools(bundle: BackendBundle) -> list[tuple[ToolDefinition, object]]:
    backend = bundle.window
    unsupported = backend is None

    async def list_windows(call: ToolCallRequest) -> ActionResult:
        windows = await backend.list_windows()  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="window.list",
            execution_time_ms=0,
            data={"windows": [w.model_dump(mode="json") for w in windows]},
        )

    async def find_window(call: ToolCallRequest) -> ActionResult:
        args = _TitleQueryArgs(**call.arguments)
        window = await backend.find_window(args.title_query)  # type: ignore[union-attr]
        if window is None:
            raise ToolLogicError(
                ErrorCategory.WINDOW_NOT_FOUND, f"No window matching '{args.title_query}'."
            )
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="window.find",
            target=args.title_query,
            execution_time_ms=0,
            data={"window": window.model_dump(mode="json")},
        )

    def _state_action(tool_id: str, method_name: str, verify_field: str | None):
        async def _run(call: ToolCallRequest) -> ActionResult:
            args = _HandleArgs(**call.arguments)
            method = getattr(backend, method_name)
            ok = await method(args.handle)
            if not ok:
                raise ToolLogicError(
                    ErrorCategory.WINDOW_NOT_FOUND, f"No window with handle '{args.handle}'."
                )
            verification = None
            if verify_field is not None:
                window = await backend.get_window(args.handle)  # type: ignore[union-attr]
                passed = window is not None and bool(getattr(window, verify_field))
                verification = VerificationOutcome(
                    passed=passed, method="window_state_detection", detail=verify_field
                )
            return ActionResult(
                status=ActionStatus.VERIFIED if verification else ActionStatus.EXECUTED,
                tool=tool_id,
                target=args.handle,
                execution_time_ms=0,
                verification=verification,
            )

        return _run

    async def close_window(call: ToolCallRequest) -> ActionResult:
        args = _HandleArgs(**call.arguments)
        ok = await backend.close_window(args.handle)  # type: ignore[union-attr]
        if not ok:
            raise ToolLogicError(
                ErrorCategory.WINDOW_NOT_FOUND, f"No window with handle '{args.handle}'."
            )
        still_present = await backend.get_window(args.handle)  # type: ignore[union-attr]
        verification = VerificationOutcome(
            passed=still_present is None, method="window_state_detection", detail="closed"
        )
        return ActionResult(
            status=ActionStatus.VERIFIED if verification.passed else ActionStatus.FAILED,
            tool="window.close",
            target=args.handle,
            execution_time_ms=0,
            verification=verification,
        )

    async def get_active(call: ToolCallRequest) -> ActionResult:
        window = await backend.get_active_window()  # type: ignore[union-attr]
        if window is None:
            raise ToolLogicError(ErrorCategory.WINDOW_NOT_FOUND, "No active window.")
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="window.get_active",
            execution_time_ms=0,
            data={"window": window.model_dump(mode="json")},
        )

    async def get_bounds(call: ToolCallRequest) -> ActionResult:
        args = _HandleArgs(**call.arguments)
        window = await backend.get_window(args.handle)  # type: ignore[union-attr]
        if window is None:
            raise ToolLogicError(
                ErrorCategory.WINDOW_NOT_FOUND, f"No window with handle '{args.handle}'."
            )
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="window.get_bounds",
            target=args.handle,
            execution_time_ms=0,
            data={"bounds": window.bounds.model_dump(mode="json") if window.bounds else None},
        )

    async def get_title(call: ToolCallRequest) -> ActionResult:
        args = _HandleArgs(**call.arguments)
        window = await backend.get_window(args.handle)  # type: ignore[union-attr]
        if window is None:
            raise ToolLogicError(
                ErrorCategory.WINDOW_NOT_FOUND, f"No window with handle '{args.handle}'."
            )
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="window.get_title",
            target=args.handle,
            execution_time_ms=0,
            data={"title": window.title},
        )

    async def control_by_title(call: ToolCallRequest) -> ActionResult:
        """Find a window by title then apply minimize/maximize/close/restore/focus in one step.
        Avoids having to chain window.find + window.* in two separate plan steps.
        Retries for up to 3 seconds so that compound commands like "open notepad and type
        hello" can immediately focus the window even if the app is still starting up."""
        import asyncio as _asyncio

        args = _ControlByTitleArgs(**call.arguments)
        window = None
        for _attempt in range(7):  # up to ~3 seconds total (0 + 6 × 0.5 s)
            window = await backend.find_window(args.title_query)  # type: ignore[union-attr]
            if window is not None:
                break
            if _attempt < 6:
                await _asyncio.sleep(0.5)
        if window is None:
            raise ToolLogicError(
                ErrorCategory.WINDOW_NOT_FOUND,
                f"No window matching '{args.title_query}'.",
            )
        action = args.action.lower()
        ok = False
        if action == "minimize":
            ok = await backend.minimize(window.handle)  # type: ignore[union-attr]
        elif action == "maximize":
            ok = await backend.maximize(window.handle)  # type: ignore[union-attr]
        elif action == "close":
            ok = await backend.close_window(window.handle)  # type: ignore[union-attr]
        elif action == "restore":
            ok = await backend.restore(window.handle)  # type: ignore[union-attr]
        else:
            ok = await backend.focus_window(window.handle)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="window.control_by_title",
            target=args.title_query,
            execution_time_ms=0,
            data={"action": action, "handle": window.handle, "title": window.title},
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "window.list",
                "List Windows",
                "Read-only: lists open windows.",
                _EmptyArgs,
                RiskLevel.SAFE,
            ),
            list_windows,
        ),
        (
            _tool(
                "window.find",
                "Find Window",
                "Read-only: finds a window by title substring.",
                _TitleQueryArgs,
                RiskLevel.SAFE,
            ),
            find_window,
        ),
        (
            _tool(
                "window.focus",
                "Focus Window",
                "Brings a window to the foreground.",
                _HandleArgs,
                RiskLevel.SAFE,
            ),
            _state_action("window.focus", "focus_window", "is_active"),
        ),
        (
            _tool(
                "window.minimize",
                "Minimize Window",
                "Minimizes a window.",
                _HandleArgs,
                RiskLevel.SAFE,
            ),
            _state_action("window.minimize", "minimize", "is_minimized"),
        ),
        (
            _tool(
                "window.maximize",
                "Maximize Window",
                "Maximizes a window.",
                _HandleArgs,
                RiskLevel.SAFE,
            ),
            _state_action("window.maximize", "maximize", "is_maximized"),
        ),
        (
            _tool(
                "window.restore",
                "Restore Window",
                "Restores a minimized/maximized window.",
                _HandleArgs,
                RiskLevel.SAFE,
            ),
            _state_action("window.restore", "restore", None),
        ),
        (
            _tool(
                "window.close",
                "Close Window",
                "Requests a graceful window close.",
                _HandleArgs,
                RiskLevel.MODERATE,
            ),
            close_window,
        ),
        (
            _tool(
                "window.get_active",
                "Get Active Window",
                "Read-only: the current foreground window.",
                _EmptyArgs,
                RiskLevel.SAFE,
            ),
            get_active,
        ),
        (
            _tool(
                "window.get_bounds",
                "Get Window Bounds",
                "Read-only: a window's screen rectangle.",
                _HandleArgs,
                RiskLevel.SAFE,
            ),
            get_bounds,
        ),
        (
            _tool(
                "window.get_title",
                "Get Window Title",
                "Read-only: a window's title text.",
                _HandleArgs,
                RiskLevel.SAFE,
            ),
            get_title,
        ),
        (
            _tool(
                "window.control_by_title",
                "Control Window by Title",
                "Find a window by title and apply an action: focus, minimize, maximize, restore, or close.",
                _ControlByTitleArgs,
                RiskLevel.MODERATE,
            ),
            control_by_title,
        ),
    ]

    result: list[tuple[ToolDefinition, object]] = []
    for definition, fn in specs:
        executor = (
            platform_unsupported_executor(definition.id)
            if unsupported
            else callable_executor(
                definition.id, fn, default_evidence_tier=EvidenceTier.NATIVE_API
            )
        )
        result.append((definition, executor))
    return result
