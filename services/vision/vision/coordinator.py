"""ObservationCoordinator — decides which perception sources are actually
needed and orchestrates them. docs/phase-3/VISUAL-PERCEPTION-ARCHITECTURE.md,
docs/phase-3/PERFORMANCE.md.

Priority order (docs/architecture/05-COMPUTER-CONTROL.md §1, restated for
perception in docs/phase-3 §3): UI Automation before OCR before vision.
`ground_target` is the concrete embodiment of 'do not run expensive vision
analysis when structured UI info already answers the question' — it tries
UIA-only grounding first and only escalates to OCR, then vision, when the
cheaper tier didn't produce a confident answer. Escalation decisions are
pure functions (`decide_next_tier`) so this policy is unit-testable
without any backend at all.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from computer_control.core.backends import ScreenBackend, UIAutomationBackend, WindowBackend
from computer_control.core.models import Rect
from veyra_contracts import ContentSource, EvidenceTier

from vision.core.cache import ObservationCache
from vision.core.confidence import requires_confirmation
from vision.core.fusion import PerceptionFusion
from vision.core.grounding import GroundingEngine
from vision.core.models import (
    GroundedElement,
    GroundingResult,
    Monitor,
    SceneGraph,
    ScreenObservation,
    TargetDescription,
)
from vision.core.privacy import PrivacyRedactor, SecretDetector, max_privacy_level
from vision.core.vision_provider import NotConfiguredVisionProvider, VisionProvider
from vision.ocr.engine import OCREngine
from vision.windows.ui_tree import capture_scene_graph


def decide_next_tier(
    *, ui_result: GroundingResult, ocr_attempted: bool, vision_available: bool
) -> str:
    """Pure escalation-decision function. Returns 'DONE', 'OCR', or
    'VISION'. UIA producing GROUNDED *or* AMBIGUOUS_TARGET both count as
    'already answered' — ambiguity is a real, structured answer (docs/phase-3
    §22), not a reason to escalate to a lower-confidence tier hoping for a
    single lucky match."""
    if ui_result.status in ("GROUNDED", "AMBIGUOUS_TARGET"):
        return "DONE"
    if not ocr_attempted:
        return "OCR"
    if vision_available:
        return "VISION"
    return "DONE"


@dataclass
class ObservationCoordinator:
    screen: ScreenBackend
    ui_automation: UIAutomationBackend | None = None
    window: WindowBackend | None = None
    ocr_engine: OCREngine = field(default_factory=OCREngine)
    vision_provider: VisionProvider = field(default_factory=NotConfiguredVisionProvider)
    fusion: PerceptionFusion = field(default_factory=PerceptionFusion)
    grounding: GroundingEngine = field(default_factory=GroundingEngine)
    redactor: PrivacyRedactor = field(default_factory=PrivacyRedactor)
    detector: SecretDetector = field(default_factory=SecretDetector)
    cache: ObservationCache = field(default_factory=ObservationCache)

    async def get_monitor_layout(self) -> list[Monitor]:
        """docs/phase-3 §12 — cross-platform (mss) monitor enumeration;
        genuinely real and tested against a real (virtual) display in this
        environment. DPI scale is filled in as 1.0 here (honest default);
        a Windows host layers the real per-monitor scale on top via
        `vision.windows.dpi.get_dpi_scale_for_window`, which this function
        deliberately does not call itself — it has no window to query a
        scale for."""
        import mss

        monitors: list[Monitor] = []
        with mss.MSS() as sct:
            for index, mon in enumerate(sct.monitors):
                if index == 0:
                    # mss.monitors[0] is the "all monitors combined"
                    # virtual screen, not a real, individually addressable
                    # monitor — see computer_control.screen's same
                    # convention.
                    continue
                monitors.append(
                    Monitor(
                        index=index,
                        bounds=Rect(
                            left=mon["left"],
                            top=mon["top"],
                            width=mon["width"],
                            height=mon["height"],
                        ),
                        dpi_scale=1.0,
                        is_primary=(index == 1),
                    )
                )
        return monitors

    async def _ui_elements(
        self, *, window_handle: str | None, window_title: str | None
    ) -> tuple[list[GroundedElement], SceneGraph | None]:
        if self.ui_automation is None:
            return [], None
        scene = await capture_scene_graph(
            self.ui_automation, window_title=window_title, window_handle=window_handle
        )
        nodes = scene.root.walk()
        elements = self.fusion.fuse(ui_nodes=nodes)
        return elements, scene

    async def _capture_for_ocr(self, *, window_handle: str | None) -> str:
        if window_handle is not None:
            result = await self.screen.capture_window(window_handle)
        else:
            result = await self.screen.capture_full()
        return result.image_base64

    async def observe(
        self,
        *,
        window_handle: str | None = None,
        window_title: str | None = None,
        include_ocr: bool = True,
        include_vision: bool = False,
        task_id: str | None = None,
        correlation_id: str | None = None,
    ) -> ScreenObservation:
        """docs/phase-3/SCREEN-OBSERVATION.md — builds one structured
        `ScreenObservation`. `include_ocr`/`include_vision` are explicit
        caller opt-ins (event-driven observation, not continuous
        high-frequency capture — docs/phase-3 §31) rather than something
        this method decides on its own; `ground_target` below is the
        method that actually implements the 'skip expensive tiers when
        cheaper ones already answered' policy."""
        timings: dict[str, int] = {}
        sources: list[EvidenceTier] = []

        window = None
        if self.window is not None:
            window = (
                await self.window.get_window(window_handle)
                if window_handle
                else await self.window.get_active_window()
            )

        t0 = time.monotonic()
        _elements, scene = await self._ui_elements(
            window_handle=window_handle, window_title=window_title
        )
        if scene is not None:
            timings["ui_automation_ms"] = int((time.monotonic() - t0) * 1000)
            sources.append(EvidenceTier.UI_AUTOMATION)

        text_regions = []
        if include_ocr:
            t1 = time.monotonic()
            image_base64 = await self._capture_for_ocr(window_handle=window_handle)
            text_regions = self.ocr_engine.extract(image_base64)
            timings["ocr_ms"] = int((time.monotonic() - t1) * 1000)
            sources.append(EvidenceTier.OCR)

        visual_regions = []
        if include_vision and not isinstance(self.vision_provider, NotConfiguredVisionProvider):
            t2 = time.monotonic()
            image_base64 = await self._capture_for_ocr(window_handle=window_handle)
            analysis = await self.vision_provider.describe_scene(image_base64)
            visual_regions = analysis.regions
            timings["vision_ms"] = int((time.monotonic() - t2) * 1000)
            if analysis.available:
                sources.append(EvidenceTier.VISION_MODEL)

        fused = self.fusion.fuse(
            ui_nodes=(scene.root.walk() if scene is not None else None),
            text_regions=text_regions,
            visual_regions=visual_regions,
        )
        redacted_text = [
            region.model_copy(
                update={
                    "text": self.redactor.redact_text(
                        region.text, self.detector.classify_text(region.text)
                    )
                }
            )
            for region in text_regions
        ]
        privacy_level = max_privacy_level([e.privacy_level for e in fused])

        observation = ScreenObservation(
            window_handle=window.handle if window else window_handle,
            window_title=window.title if window else window_title,
            scene=scene,
            text_regions=redacted_text,
            visual_regions=visual_regions,
            privacy_level=privacy_level,
            source=ContentSource.UI_OBSERVATION,
            task_id=task_id,
            correlation_id=correlation_id,
            stage_timings_ms=timings,
            sources_used=sources,
        )
        observation.screenshot_ref = self.cache.put(observation)
        return observation

    async def ground_target(
        self,
        target: TargetDescription,
        *,
        window_handle: str | None = None,
        window_title: str | None = None,
    ) -> GroundingResult:
        """docs/phase-3 §22/final acceptance tests — grounds a target,
        escalating tiers only as needed (`decide_next_tier`). Never clicks
        or otherwise acts (docs/phase-3 §35/§56) — returns a structured
        result only."""
        ui_elements, _scene = await self._ui_elements(
            window_handle=window_handle, window_title=window_title
        )
        result = self.grounding.ground(target, ui_elements)
        tier = decide_next_tier(
            ui_result=result,
            ocr_attempted=False,
            vision_available=not isinstance(self.vision_provider, NotConfiguredVisionProvider),
        )
        elements = ui_elements
        if tier == "OCR":
            image_base64 = await self._capture_for_ocr(window_handle=window_handle)
            text_regions = self.ocr_engine.extract(image_base64)
            elements = elements + self.fusion.fuse(text_regions=text_regions)
            result = self.grounding.ground(target, elements)
            tier = decide_next_tier(ui_result=result, ocr_attempted=True, vision_available=(
                not isinstance(self.vision_provider, NotConfiguredVisionProvider)
            ))
        if tier == "VISION":
            image_base64 = await self._capture_for_ocr(window_handle=window_handle)
            visual = await self.grounding.find_by_visual_similarity(
                target, image_base64, self.vision_provider
            )
            elements = elements + visual
            result = self.grounding.ground(target, elements)
        return result

    def requires_fresh_confirmation(self, element: GroundedElement) -> bool:
        """docs/phase-3 §21 — CRITICAL-risk actions must never be
        authorized purely from a low-confidence grounded target; this is
        the one function callers (a future planner, or Phase 2's
        SENSITIVE/CRITICAL confirmation path) should consult before acting
        on a `GroundedElement`."""
        return requires_confirmation(element.confidence_score)
