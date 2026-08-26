"""filesystem.* tools. docs/phase-2/FILESYSTEM-CONTROL.md.

Genuinely cross-platform and genuinely tested in this environment (no
platform gate) — see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2.
`filesystem.delete` is deliberately absent: there is no function on
FilesystemEngine that deletes anything, so there is nothing here to wire
up even by mistake.

Risk tiers: search/list_directory/get_metadata/open are SAFE (matches the
product brief's own 'search files'/'open application' SAFE examples);
create_folder/create_file/copy/move/rename are MODERATE (matches the
brief's own 'create folder, rename file, move file' MODERATE examples).
"""

from __future__ import annotations

from computer_control.core.results import ActionResult, ActionStatus, VerificationOutcome
from computer_control.filesystem import FilesystemEngine
from computer_control.filesystem.engine import FilesystemError
from computer_control.filesystem.models import SearchCriteria
from computer_control.filesystem.path_policy import PathNotAllowedError, PathProtectedError
from computer_control.launcher import NoAssociatedApplicationLauncherError, default_launcher
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

from app.services.computer_control.support import ToolFn, ToolLogicError, callable_executor


class _PathArgs(BaseModel):
    path: str


class _CreateArgs(BaseModel):
    parent: str
    name: str
    content: str = ""


class _CopyMoveArgs(BaseModel):
    source: str
    destination: str


class _RenameArgs(BaseModel):
    path: str
    new_name: str


def _tool(tool_id: str, name: str, description: str, args_model: type[BaseModel], risk: RiskLevel):
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=ToolCategory.FILESYSTEM,
        input_schema=args_model.model_json_schema(),
        output_schema={"type": "object"},
        risk_level=risk,
        required_permission=f"computer_control.{tool_id}",
        confirmation_policy=(
            ConfirmationPolicy.NEVER if risk == RiskLevel.SAFE else ConfirmationPolicy.SESSION
        ),
        verification_strategy="filesystem_state_detection",
        timeout_seconds=30,
    )


def _wrap(fn):
    async def _run(call: ToolCallRequest) -> ActionResult:
        try:
            return await fn(call)
        except (PathNotAllowedError, PathProtectedError, FilesystemError) as exc:
            raise ToolLogicError(exc.code, str(exc)) from exc
        except NoAssociatedApplicationLauncherError as exc:
            # docs/phase-2/FILESYSTEM-CONTROL.md §7.3 — this host has no
            # 'xdg-open'/'open' to hand the file to; found via Phase 4's
            # real end-to-end task execution (docs/phase-4/PHASE-4-TEST-RESULTS.md),
            # previously an unhandled exception that crashed the caller
            # instead of a structured failure.
            raise ToolLogicError(ErrorCategory.APPLICATION_LAUNCH_FAILED, str(exc)) from exc

    return _run


def build_filesystem_tools(engine: FilesystemEngine) -> list[tuple[ToolDefinition, object]]:
    async def search(call: ToolCallRequest) -> ActionResult:
        criteria = SearchCriteria(**call.arguments)
        matches = await engine.search(criteria)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="filesystem.search",
            target=criteria.directory,
            execution_time_ms=0,
            data={"matches": [m.model_dump(mode="json") for m in matches]},
        )

    async def list_directory(call: ToolCallRequest) -> ActionResult:
        args = _PathArgs(**call.arguments)
        entries = await engine.list_directory(args.path)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="filesystem.list_directory",
            target=args.path,
            execution_time_ms=0,
            data={"entries": [e.model_dump(mode="json") for e in entries]},
        )

    async def get_metadata(call: ToolCallRequest) -> ActionResult:
        args = _PathArgs(**call.arguments)
        metadata = await engine.get_metadata(args.path)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="filesystem.get_metadata",
            target=args.path,
            execution_time_ms=0,
            data={"metadata": metadata.model_dump(mode="json")},
        )

    async def open_file(call: ToolCallRequest) -> ActionResult:
        args = _PathArgs(**call.arguments)
        await engine.open_file(args.path, default_launcher())
        # docs/phase-2 §7.3: never claim success merely because the
        # launch call returned — but this engine has no reliable
        # cross-application way to confirm a viewer window appeared, so
        # it honestly reports EXECUTED (launch attempted, not verified)
        # rather than fabricating a VERIFIED result.
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="filesystem.open",
            target=args.path,
            execution_time_ms=0,
            verification=VerificationOutcome(
                passed=False,
                method="none",
                detail="No cross-application way to verify the associated "
                "viewer actually opened; status intentionally left as "
                "EXECUTED, not VERIFIED.",
            ),
        )

    async def create_folder(call: ToolCallRequest) -> ActionResult:
        args = _CreateArgs(**call.arguments)
        metadata = await engine.create_folder(args.parent, args.name)
        verification = VerificationOutcome(
            passed=metadata.is_directory, method="filesystem_state_detection"
        )
        return ActionResult(
            status=ActionStatus.VERIFIED,
            tool="filesystem.create_folder",
            target=metadata.path,
            execution_time_ms=0,
            verification=verification,
            data={"metadata": metadata.model_dump(mode="json")},
        )

    async def create_file(call: ToolCallRequest) -> ActionResult:
        args = _CreateArgs(**call.arguments)
        metadata = await engine.create_file(args.parent, args.name, args.content)
        verification = VerificationOutcome(
            passed=not metadata.is_directory, method="filesystem_state_detection"
        )
        return ActionResult(
            status=ActionStatus.VERIFIED,
            tool="filesystem.create_file",
            target=metadata.path,
            execution_time_ms=0,
            verification=verification,
            data={"metadata": metadata.model_dump(mode="json")},
        )

    async def copy(call: ToolCallRequest) -> ActionResult:
        args = _CopyMoveArgs(**call.arguments)
        metadata = await engine.copy(args.source, args.destination)
        return ActionResult(
            status=ActionStatus.VERIFIED,
            tool="filesystem.copy",
            target=metadata.path,
            execution_time_ms=0,
            verification=VerificationOutcome(passed=True, method="filesystem_state_detection"),
            data={"metadata": metadata.model_dump(mode="json")},
        )

    async def move(call: ToolCallRequest) -> ActionResult:
        args = _CopyMoveArgs(**call.arguments)
        metadata = await engine.move(args.source, args.destination)
        return ActionResult(
            status=ActionStatus.VERIFIED,
            tool="filesystem.move",
            target=metadata.path,
            execution_time_ms=0,
            verification=VerificationOutcome(passed=True, method="filesystem_state_detection"),
            data={"metadata": metadata.model_dump(mode="json")},
        )

    async def rename(call: ToolCallRequest) -> ActionResult:
        args = _RenameArgs(**call.arguments)
        metadata = await engine.rename(args.path, args.new_name)
        return ActionResult(
            status=ActionStatus.VERIFIED,
            tool="filesystem.rename",
            target=metadata.path,
            execution_time_ms=0,
            verification=VerificationOutcome(passed=True, method="filesystem_state_detection"),
            data={"metadata": metadata.model_dump(mode="json")},
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "filesystem.search",
                "Search Files",
                "Read-only: searches a directory for matching files.",
                SearchCriteria,
                RiskLevel.SAFE,
            ),
            search,
        ),
        (
            _tool(
                "filesystem.list_directory",
                "List Directory",
                "Read-only: lists a directory's contents.",
                _PathArgs,
                RiskLevel.SAFE,
            ),
            list_directory,
        ),
        (
            _tool(
                "filesystem.get_metadata",
                "Get File Metadata",
                "Read-only: file/folder metadata.",
                _PathArgs,
                RiskLevel.SAFE,
            ),
            get_metadata,
        ),
        (
            _tool(
                "filesystem.open",
                "Open File",
                "Opens a file with its associated application.",
                _PathArgs,
                RiskLevel.SAFE,
            ),
            open_file,
        ),
        (
            _tool(
                "filesystem.create_folder",
                "Create Folder",
                "Creates a new folder.",
                _CreateArgs,
                RiskLevel.MODERATE,
            ),
            create_folder,
        ),
        (
            _tool(
                "filesystem.create_file",
                "Create File",
                "Creates a new file.",
                _CreateArgs,
                RiskLevel.MODERATE,
            ),
            create_file,
        ),
        (
            _tool(
                "filesystem.copy",
                "Copy File",
                "Copies a file or folder.",
                _CopyMoveArgs,
                RiskLevel.MODERATE,
            ),
            copy,
        ),
        (
            _tool(
                "filesystem.move",
                "Move File",
                "Moves a file or folder.",
                _CopyMoveArgs,
                RiskLevel.MODERATE,
            ),
            move,
        ),
        (
            _tool(
                "filesystem.rename",
                "Rename File",
                "Renames a file or folder.",
                _RenameArgs,
                RiskLevel.MODERATE,
            ),
            rename,
        ),
    ]

    return [
        (
            definition,
            callable_executor(
                definition.id, _wrap(fn), default_evidence_tier=EvidenceTier.NATIVE_API
            ),
        )
        for definition, fn in specs
    ]
