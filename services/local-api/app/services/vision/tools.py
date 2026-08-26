"""screen.observe / screen.capture_region / ui.get_tree / ui.find_all /
ocr.extract / vision.analyze / vision.locate / scene.diff / target.ground.

docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §6 — every tool here is
read-only perception; nothing in this module moves a mouse, types a key,
or clicks anything (Phase 2 already owns every action). Risk tiers:
`screen.capture_region` is MODERATE (matches the other `screen.*` tools);
every other tool here is SAFE. `screen.observe` and `target.ground` are
additionally gated by `screen_observation.enabled`
(app/services/vision/gating.py) because their internal OCR/vision
fallback tiers can capture pixels; `ui.get_tree`/`ui.find_all` are
platform-gated (Windows-only UI Automation) the same way Phase 2's
`ui.find`/`ui.click` already are.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from computer_control.core.models import Rect
from computer_control.core.results import ActionResult, ActionStatus
from computer_control.core.selectors import UISelector
from pydantic import BaseModel, Field
from veyra_contracts import (
    ConfirmationPolicy,
    ErrorCategory,
    EvidenceTier,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
)
from vision.coordinator import ObservationCoordinator
from vision.core.diff import compute_scene_diff
from vision.core.models import SceneGraph, TargetDescription
from vision.core.vision_provider import VisionProvider
from vision.ocr.engine import OCREngine, OCRUnavailableError
from vision.windows.ui_tree import capture_scene_graph

from app.services.computer_control.backends import BackendBundle
from app.services.computer_control.support import (
    ToolFn,
    ToolLogicError,
    callable_executor,
    platform_unsupported_executor,
)
from app.services.vision.gating import screen_observation_enabled


class _EmptyArgs(BaseModel):
    pass


class _CaptureRegionArgs(BaseModel):
    bounds: Rect
    display_index: int = 1


class _ObserveArgs(BaseModel):
    window_handle: str | None = None
    include_ocr: bool = True
    include_vision: bool = False


class _TreeArgs(BaseModel):
    window_title: str | None = None
    max_depth: int = Field(default=8, ge=1, le=32)


class _FindAllArgs(BaseModel):
    selector: UISelector


class _OcrArgs(BaseModel):
    image_base64: str
    languages: list[str] = Field(default_factory=lambda: ["eng"])


class _AnalyzeArgs(BaseModel):
    image_base64: str
    prompt: str = "Describe what is on this screen."


class _LocateArgs(BaseModel):
    image_base64: str
    target: TargetDescription


class _DiffArgs(BaseModel):
    before: SceneGraph
    after: SceneGraph


class _GroundArgs(BaseModel):
    target: TargetDescription
    window_handle: str | None = None
    window_title: str | None = None


def _tool(
    tool_id: str,
    category: ToolCategory,
    name: str,
    description: str,
    args_model: type[BaseModel],
    risk: RiskLevel = RiskLevel.SAFE,
    *,
    timeout_seconds: int = 30,
) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=category,
        input_schema=args_model.model_json_schema(),
        output_schema={"type": "object"},
        risk_level=risk,
        required_permission=f"computer_control.{tool_id}",
        confirmation_policy=(
            ConfirmationPolicy.NEVER if risk == RiskLevel.SAFE else ConfirmationPolicy.SESSION
        ),
        verification_strategy="none — perception tools produce evidence, they don't act.",
        timeout_seconds=timeout_seconds,
    )


def _gated(
    fn: Callable[[ToolCallRequest], Awaitable[ActionResult]],
) -> Callable[[ToolCallRequest], Awaitable[ActionResult]]:
    """docs/phase-3/PRIVACY.md — the same explicit-opt-in gate every
    pixel-capturing tool in this codebase uses (screen_tools.py's
    identical pattern), applied to the Phase 3 tools that can themselves
    capture pixels."""

    async def _run(call: ToolCallRequest) -> ActionResult:
        if not await screen_observation_enabled():
            raise ToolLogicError(
                ErrorCategory.PERMISSION_DENIED,
                "Screen observation is not enabled — see the "
                "'screen_observation.enabled' system setting "
                "(docs/security/05-DATA-PROTECTION.md §3).",
            )
        return await fn(call)

    return _run


def build_vision_tools(
    bundle: BackendBundle,
    coordinator: ObservationCoordinator,
    ocr_engine: OCREngine,
    vision_provider: VisionProvider,
) -> list[tuple[ToolDefinition, object]]:
    ui_supported = bundle.ui_automation is not None

    async def capture_region(call: ToolCallRequest) -> ActionResult:
        args = _CaptureRegionArgs(**call.arguments)
        result = await bundle.screen.capture_region(args.bounds, args.display_index)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="screen.capture_region",
            execution_time_ms=0,
            data={"capture": result.model_dump(mode="json")},
        )

    async def observe(call: ToolCallRequest) -> ActionResult:
        args = _ObserveArgs(**call.arguments)
        observation = await coordinator.observe(
            window_handle=args.window_handle,
            include_ocr=args.include_ocr,
            include_vision=args.include_vision,
            correlation_id=call.correlation_id,
        )
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="screen.observe",
            execution_time_ms=0,
            evidence_tier=(
                observation.sources_used[0] if observation.sources_used else None
            ),
            data={"observation": observation.model_dump(mode="json")},
        )

    async def get_tree(call: ToolCallRequest) -> ActionResult:
        args = _TreeArgs(**call.arguments)
        scene = await capture_scene_graph(
            bundle.ui_automation,  # type: ignore[arg-type]
            window_title=args.window_title,
            max_depth=args.max_depth,
        )
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="ui.get_tree",
            target=args.window_title,
            execution_time_ms=0,
            data={"scene": scene.model_dump(mode="json")},
        )

    async def find_all(call: ToolCallRequest) -> ActionResult:
        args = _FindAllArgs(**call.arguments)
        elements = await bundle.ui_automation.find_all(args.selector)  # type: ignore[union-attr]
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="ui.find_all",
            execution_time_ms=0,
            data={"elements": [e.model_dump(mode="json") for e in elements]},
        )

    async def ocr_extract(call: ToolCallRequest) -> ActionResult:
        args = _OcrArgs(**call.arguments)
        try:
            regions = ocr_engine.extract(args.image_base64, languages=tuple(args.languages))
        except (OCRUnavailableError, ValueError) as exc:
            raise ToolLogicError(ErrorCategory.TOOL_FAILURE, str(exc)) from exc
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="ocr.extract",
            execution_time_ms=0,
            evidence_tier=EvidenceTier.OCR,
            data={"text_regions": [r.model_dump(mode="json") for r in regions]},
        )

    async def vision_analyze(call: ToolCallRequest) -> ActionResult:
        args = _AnalyzeArgs(**call.arguments)
        result = await vision_provider.analyze_image(args.image_base64, args.prompt)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="vision.analyze",
            execution_time_ms=0,
            evidence_tier=EvidenceTier.VISION_MODEL,
            data={
                "available": result.available,
                "description": result.description,
                "reason": result.reason,
                "regions": [r.model_dump(mode="json") for r in result.regions],
            },
        )

    async def vision_locate(call: ToolCallRequest) -> ActionResult:
        args = _LocateArgs(**call.arguments)
        regions = await vision_provider.locate_target(args.image_base64, args.target)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="vision.locate",
            execution_time_ms=0,
            evidence_tier=EvidenceTier.VISION_MODEL,
            data={"regions": [r.model_dump(mode="json") for r in regions]},
        )

    async def scene_diff(call: ToolCallRequest) -> ActionResult:
        args = _DiffArgs(**call.arguments)
        diff = compute_scene_diff(args.before, args.after)
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="scene.diff",
            execution_time_ms=0,
            data={"diff": diff.model_dump(mode="json")},
        )

    async def target_ground(call: ToolCallRequest) -> ActionResult:
        args = _GroundArgs(**call.arguments)
        result = await coordinator.ground_target(
            args.target, window_handle=args.window_handle, window_title=args.window_title
        )
        # docs/phase-3 §22, Final/Second Acceptance Tests — GROUNDED and
        # AMBIGUOUS_TARGET are both legitimate, non-error outcomes;
        # NOT_FOUND is reported as EXECUTED-with-empty-result too. This
        # tool never raises just because a target wasn't (confidently)
        # found — the caller decides what to do with the structured
        # status, per docs/phase-3 §35's AI safety boundary.
        evidence_tier = None
        if result.target is not None and result.target.sources:
            evidence_tier = result.target.sources[0]
        return ActionResult(
            status=ActionStatus.EXECUTED,
            tool="target.ground",
            target=args.target.text or args.target.name,
            execution_time_ms=0,
            evidence_tier=evidence_tier,
            data={"grounding": result.model_dump(mode="json")},
        )

    specs: list[tuple[ToolDefinition, ToolFn]] = [
        (
            _tool(
                "screen.capture_region",
                ToolCategory.SCREEN,
                "Capture Screen Region",
                "Captures an explicit sub-rectangle of a display.",
                _CaptureRegionArgs,
                RiskLevel.MODERATE,
            ),
            _gated(capture_region),
        ),
        (
            _tool(
                "screen.observe",
                ToolCategory.VISION,
                "Observe Screen",
                "Read-only: builds a structured ScreenObservation (UI tree + "
                "OCR text + privacy classification) for a window.",
                _ObserveArgs,
            ),
            _gated(observe),
        ),
        (
            _tool(
                "ui.get_tree",
                ToolCategory.WINDOWS,
                "Get UI Tree",
                "Read-only: the full normalized UI element tree of a window.",
                _TreeArgs,
            ),
            get_tree,
        ),
        (
            _tool(
                "ui.find_all",
                ToolCategory.WINDOWS,
                "Find All UI Elements",
                "Read-only: every UI element matching a selector.",
                _FindAllArgs,
            ),
            find_all,
        ),
        (
            _tool(
                "ocr.extract",
                ToolCategory.VISION,
                "Extract Text (OCR)",
                "Read-only: extracts text regions with confidence from an "
                "already-captured image (English/Tamil).",
                _OcrArgs,
            ),
            ocr_extract,
        ),
        (
            _tool(
                "vision.analyze",
                ToolCategory.VISION,
                "Analyze Image",
                "Read-only: describes an already-captured image via the "
                "configured vision provider (none configured in Phase 3).",
                _AnalyzeArgs,
            ),
            vision_analyze,
        ),
        (
            _tool(
                "vision.locate",
                ToolCategory.VISION,
                "Locate Target (Vision)",
                "Read-only: locates a described target within an "
                "already-captured image via the configured vision provider.",
                _LocateArgs,
            ),
            vision_locate,
        ),
        (
            _tool(
                "scene.diff",
                ToolCategory.VISION,
                "Diff Scenes",
                "Read-only: computes added/removed/changed/moved between "
                "two previously captured UI trees.",
                _DiffArgs,
            ),
            scene_diff,
        ),
        (
            _tool(
                "target.ground",
                ToolCategory.VISION,
                "Ground Target",
                "Read-only: resolves a described target to a GroundedElement, "
                "escalating UIA -> OCR -> vision only as needed; returns "
                "AMBIGUOUS_TARGET rather than guessing.",
                _GroundArgs,
            ),
            _gated(target_ground),
        ),
    ]

    result: list[tuple[ToolDefinition, object]] = []
    for definition, fn in specs:
        needs_ui = definition.id in ("ui.get_tree", "ui.find_all")
        executor = (
            platform_unsupported_executor(definition.id)
            if needs_ui and not ui_supported
            else callable_executor(
                definition.id,
                fn,
                default_evidence_tier=(
                    EvidenceTier.UI_AUTOMATION if needs_ui else None
                ),
            )
        )
        result.append((definition, executor))
    return result
