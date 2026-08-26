"""screen.* tools. docs/phase-2/SCREEN-CAPTURE.md.

Gated by the `screen_observation.enabled` SystemSetting — seeded OFF by
default in Phase 1 (docs/security/05-DATA-PROTECTION.md §3) and still OFF
by default here; a screen capture tool call is refused with
PERMISSION_DENIED unless a user has explicitly turned this on, *in
addition to* the normal Policy Engine grant check for the MODERATE risk
tier. This is the one piece of Phase 1 continuity Phase 2 was specifically
designed to complete: the setting existed with nothing checking it before.

Risk tier: MODERATE — not SAFE, because a capture can contain sensitive
on-screen content; not SENSITIVE/CRITICAL, because it never leaves the
local machine (docs/phase-2 §14, §29).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from computer_control.core.results import ActionResult, ActionStatus
from computer_control.screen import NoActiveWindowError, WindowNotFoundForCaptureError
from pydantic import BaseModel
from sqlalchemy import select
from veyra_contracts import (
    ConfirmationPolicy,
    ErrorCategory,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
)

from app.db.session import SessionLocal
from app.models.setting import SystemSetting
from app.services.computer_control.backends import BackendBundle
from app.services.computer_control.support import ToolFn, ToolLogicError, callable_executor


class _EmptyArgs(BaseModel):
    pass


class _HandleArgs(BaseModel):
    handle: str


async def screen_observation_enabled() -> bool:
    async with SessionLocal() as session:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "screen_observation.enabled")
        )
        row = result.scalars().first()
        return bool(row.value) if row is not None else False


def _tool(tool_id: str, name: str, description: str, args_model: type[BaseModel]):
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=ToolCategory.SCREEN,
        input_schema=args_model.model_json_schema(),
        output_schema={"type": "object"},
        risk_level=RiskLevel.MODERATE,
        required_permission=f"computer_control.{tool_id}",
        confirmation_policy=ConfirmationPolicy.SESSION,
        verification_strategy="none — a returned image is its own evidence.",
    )


def _wrap(
    fn: Callable[[ToolCallRequest], Awaitable[ActionResult]],
    is_enabled: Callable[[], Awaitable[bool]],
):
    async def _run(call: ToolCallRequest) -> ActionResult:
        if not await is_enabled():
            raise ToolLogicError(
                ErrorCategory.PERMISSION_DENIED,
                "Screen observation is not enabled — see the "
                "'screen_observation.enabled' system setting "
                "(docs/security/05-DATA-PROTECTION.md §3).",
            )
        try:
            return await fn(call)
        except (WindowNotFoundForCaptureError, NoActiveWindowError) as exc:
            raise ToolLogicError(exc.code, str(exc)) from exc

    return _run


def build_screen_tools(
    bundle: BackendBundle,
    is_enabled: Callable[[], Awaitable[bool]] = screen_observation_enabled,
) -> list[tuple[ToolDefinition, object]]:
    screen = bundle.screen

    async def capture(call: ToolCallRequest) -> ActionResult:
        result = await screen.capture_full()
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="screen.capture",
            execution_time_ms=0,
            data={"capture": result.model_dump(mode="json")},
        )

    async def capture_window(call: ToolCallRequest) -> ActionResult:
        args = _HandleArgs(**call.arguments)
        result = await screen.capture_window(args.handle)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="screen.capture_window",
            target=args.handle,
            execution_time_ms=0,
            data={"capture": result.model_dump(mode="json")},
        )

    async def capture_active_window(call: ToolCallRequest) -> ActionResult:
        result = await screen.capture_active_window()
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="screen.capture_active_window",
            execution_time_ms=0,
            data={"capture": result.model_dump(mode="json")},
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "screen.capture", "Capture Screen", "Captures the primary display.", _EmptyArgs
            ),
            capture,
        ),
        (
            _tool(
                "screen.capture_window",
                "Capture Window",
                "Captures a specific window.",
                _HandleArgs,
            ),
            capture_window,
        ),
        (
            _tool(
                "screen.capture_active_window",
                "Capture Active Window",
                "Captures the current foreground window.",
                _EmptyArgs,
            ),
            capture_active_window,
        ),
    ]

    return [
        (definition, callable_executor(definition.id, _wrap(fn, is_enabled)))
        for definition, fn in specs
    ]
