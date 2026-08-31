"""application.* tools. docs/phase-2/APPLICATION-CONTROL.md.

Risk tiers: list_running/find/focus/is_running are SAFE (read-only or as
cosmetic as window focus); launch is SAFE per the original product
brief's own example ('SAFE: ... open application'); close is MODERATE
(reversible, but can prompt the app's own unsaved-changes dialog).
"""

from __future__ import annotations

from computer_control.core.results import ActionResult, ActionStatus, VerificationOutcome
from computer_control.registry import (
    ApplicationDisabledError,
    ApplicationNotFoundError,
    ApplicationRegistry,
)
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


class _FindArgs(BaseModel):
    query: str


class _LaunchArgs(BaseModel):
    application: str
    args: list[str] = []


class _ProcessIdArgs(BaseModel):
    process_id: int


def _tool(tool_id: str, name: str, description: str, args_model: type[BaseModel], risk: RiskLevel):
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=ToolCategory.SYSTEM,
        input_schema=args_model.model_json_schema(),
        output_schema={"type": "object"},
        risk_level=risk,
        required_permission=f"computer_control.{tool_id}",
        confirmation_policy=(
            ConfirmationPolicy.NEVER if risk == RiskLevel.SAFE else ConfirmationPolicy.SESSION
        ),
        verification_strategy="process_and_window_detection",
    )


def build_application_tools(
    bundle: BackendBundle, registry: ApplicationRegistry
) -> list[tuple[ToolDefinition, object]]:
    backend = bundle.application
    unsupported = backend is None

    async def list_running(call: ToolCallRequest) -> ActionResult:
        apps = await backend.list_running()  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="application.list_running",
            execution_time_ms=0,
            data={"applications": [a.model_dump(mode="json") for a in apps]},
        )

    async def find(call: ToolCallRequest) -> ActionResult:
        args = _FindArgs(**call.arguments)
        apps = await backend.find(args.query)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="application.find",
            target=args.query,
            execution_time_ms=0,
            data={"applications": [a.model_dump(mode="json") for a in apps]},
        )

    async def launch(call: ToolCallRequest) -> ActionResult:
        args = _LaunchArgs(**call.arguments)
        try:
            executable_path = registry.resolve(args.application)
        except ApplicationNotFoundError as exc:
            raise ToolLogicError(ErrorCategory.APPLICATION_NOT_FOUND, str(exc)) from exc
        except ApplicationDisabledError as exc:
            raise ToolLogicError(ErrorCategory.TOOL_DISABLED, str(exc)) from exc

        try:
            app_info = await backend.launch(executable_path, args.args)  # type: ignore[union-attr]
        except FileNotFoundError as exc:
            raise ToolLogicError(ErrorCategory.APPLICATION_LAUNCH_FAILED, str(exc)) from exc
        except OSError as exc:
            raise ToolLogicError(ErrorCategory.APPLICATION_LAUNCH_FAILED, str(exc)) from exc

        # Verification, per docs/phase-2 §21: a launch call returning
        # without error is NOT sufficient — confirm the process actually
        # exists before claiming VERIFIED.
        #
        # Brief sleep before the first PID check: some executables
        # (notably Windows 10/11 Notepad) are UWP stubs that spawn the
        # real process and exit within milliseconds, making an instant
        # psutil.pid_exists() call unreliable.
        import asyncio as _asyncio
        await _asyncio.sleep(0.5)
        still_running = await backend.is_running(app_info.process_id)  # type: ignore[union-attr]
        if not still_running:
            # Stub may have exited after launching the real (UWP) process.
            # Fall back to a name-based search so a UWP Notepad, Calculator,
            # etc. isn't falsely reported as failed when it is visibly open.
            running_by_name = await backend.find(args.application)  # type: ignore[union-attr]
            still_running = len(running_by_name) > 0

        verification = VerificationOutcome(
            passed=still_running,
            method="process_detection",
            detail=f"pid={app_info.process_id}",
        )
        # If the launch call succeeded without an exception, the OS accepted
        # the request. Downgrade to EXECUTED (not FAILED) when we can't
        # confirm the PID — the app may still be open (UWP stub scenario).
        if still_running:
            status = ActionStatus.VERIFIED
        else:
            status = ActionStatus.EXECUTED
        return ActionResult(
            status=status,
            tool="application.launch",
            target=args.application,
            execution_time_ms=0,
            verification=verification,
            data={"application": app_info.model_dump(mode="json")},
        )

    async def focus(call: ToolCallRequest) -> ActionResult:
        args = _ProcessIdArgs(**call.arguments)
        ok = await backend.focus(args.process_id)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED if ok else ActionStatus.FAILED,
            tool="application.focus",
            target=str(args.process_id),
            execution_time_ms=0,
        )

    async def is_running(call: ToolCallRequest) -> ActionResult:
        args = _ProcessIdArgs(**call.arguments)
        running = await backend.is_running(args.process_id)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="application.is_running",
            target=str(args.process_id),
            execution_time_ms=0,
            data={"running": running},
        )

    async def close(call: ToolCallRequest) -> ActionResult:
        args = _ProcessIdArgs(**call.arguments)
        ok = await backend.close(args.process_id)  # type: ignore[union-attr]
        still_running = await backend.is_running(args.process_id) if ok else True  # type: ignore[union-attr]
        verification = VerificationOutcome(
            passed=ok and not still_running,
            method="process_detection",
            detail=f"pid={args.process_id}",
        )
        return ActionResult(
            status=ActionStatus.VERIFIED if verification.passed else ActionStatus.FAILED,
            tool="application.close",
            target=str(args.process_id),
            execution_time_ms=0,
            verification=verification,
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "application.list_running",
                "List Running Applications",
                "Read-only: lists currently running applications.",
                _EmptyArgs,
                RiskLevel.SAFE,
            ),
            list_running,
        ),
        (
            _tool(
                "application.find",
                "Find Application",
                "Read-only: finds running applications matching a query.",
                _FindArgs,
                RiskLevel.SAFE,
            ),
            find,
        ),
        (
            _tool(
                "application.launch",
                "Launch Application",
                "Launches a registered, known application by name/alias — "
                "never an arbitrary caller-supplied path.",
                _LaunchArgs,
                RiskLevel.SAFE,
            ),
            launch,
        ),
        (
            _tool(
                "application.focus",
                "Focus Application",
                "Brings a running application's window to the foreground.",
                _ProcessIdArgs,
                RiskLevel.SAFE,
            ),
            focus,
        ),
        (
            _tool(
                "application.is_running",
                "Is Application Running",
                "Read-only: checks whether a process ID is still running.",
                _ProcessIdArgs,
                RiskLevel.SAFE,
            ),
            is_running,
        ),
        (
            _tool(
                "application.close",
                "Close Application",
                "Requests a graceful, application-level close (like "
                "clicking its close button) — never force process "
                "termination.",
                _ProcessIdArgs,
                RiskLevel.MODERATE,
            ),
            close,
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
