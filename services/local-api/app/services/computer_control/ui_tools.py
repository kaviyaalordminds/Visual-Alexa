"""ui.* tools. docs/phase-2/WINDOWS-UI-AUTOMATION.md, §12, §13.

find/wait_for are SAFE (read-only discovery); click/type are SENSITIVE,
same reasoning as mouse.click/keyboard.type.
"""

from __future__ import annotations

from computer_control.core.results import ActionResult, ActionStatus
from computer_control.core.selectors import UISelector
from computer_control.core.waiting import (
    DEFAULT_TIMEOUT_SECONDS,
    UIElementNotFoundError,
    wait_for_element,
)
from pydantic import BaseModel
from veyra_contracts import (
    ConfirmationPolicy,
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


class _FindArgs(BaseModel):
    selector: UISelector
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


class _TypeArgs(BaseModel):
    selector: UISelector
    text: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


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
        verification_strategy="post_action_element_state_check",
        timeout_seconds=15,
    )


def build_ui_tools(bundle: BackendBundle) -> list[tuple[ToolDefinition, object]]:
    backend = bundle.ui_automation
    unsupported = backend is None

    async def find(call: ToolCallRequest) -> ActionResult:
        args = _FindArgs(**call.arguments)
        try:
            element = await wait_for_element(
                backend, args.selector, timeout_seconds=args.timeout_seconds  # type: ignore[arg-type]
            )
        except UIElementNotFoundError as exc:
            raise ToolLogicError(exc.code, str(exc)) from exc
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="ui.find",
            execution_time_ms=0,
            data={"element": element.model_dump(mode="json")},
        )

    async def wait_for(call: ToolCallRequest) -> ActionResult:
        # Same underlying operation as `find` — `ui.wait_for` is exposed
        # separately per docs/phase-2 §13 because callers reason about it
        # differently ("wait until this appears" vs. "look for this"),
        # even though the implementation is identical.
        return await find(call)

    async def click(call: ToolCallRequest) -> ActionResult:
        args = _FindArgs(**call.arguments)
        ok = await backend.click_element(args.selector, args.timeout_seconds)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="ui.click",
            target=args.selector.name or args.selector.automation_id,
            execution_time_ms=0,
        )

    async def type_into(call: ToolCallRequest) -> ActionResult:
        args = _TypeArgs(**call.arguments)
        ok = await backend.type_into_element(  # type: ignore[union-attr]
            args.selector, args.text, args.timeout_seconds
        )
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="ui.type",
            target=args.selector.name or args.selector.automation_id,
            execution_time_ms=0,
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "ui.find",
                "Find UI Element",
                "Read-only: finds a UI element by selector.",
                _FindArgs,
                RiskLevel.SAFE,
            ),
            find,
        ),
        (
            _tool(
                "ui.wait_for",
                "Wait For UI Element",
                "Read-only: waits for a UI element to appear.",
                _FindArgs,
                RiskLevel.SAFE,
            ),
            wait_for,
        ),
        (
            _tool(
                "ui.click",
                "Click UI Element",
                "Clicks a UI element resolved by selector.",
                _FindArgs,
                RiskLevel.SENSITIVE,
            ),
            click,
        ),
        (
            _tool(
                "ui.type",
                "Type Into UI Element",
                "Types text into a UI element resolved by selector.",
                _TypeArgs,
                RiskLevel.SENSITIVE,
            ),
            type_into,
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
    return result
