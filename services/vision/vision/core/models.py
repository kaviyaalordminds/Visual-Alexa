"""Platform-independent perception data models. docs/phase-3/SCREEN-OBSERVATION.md,
docs/phase-3/SCENE-GRAPH.md, docs/phase-3/VISUAL-GROUNDING.md,
docs/phase-3/SCENE-DIFF.md.

None of these are persisted (docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md
§7) — they are computed on demand and returned directly in a tool result,
which already flows into the existing Phase 1 AuditLog.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from computer_control.core.models import Rect, UIElementNode
from pydantic import BaseModel, Field
from veyra_contracts import Confidence, ContentSource, EvidenceTier

from vision.core.privacy import PrivacyLevel


def _new_id() -> str:
    return uuid.uuid4().hex


class Monitor(BaseModel):
    """docs/phase-3/PERFORMANCE.md, DPI test — one physical/logical
    display. `dpi_scale` of 1.5 means 150% Windows display scaling."""

    index: int
    bounds: Rect
    dpi_scale: float = 1.0
    is_primary: bool = False


class CoordinateSpace(BaseModel):
    """docs/phase-3 §12 — 'never assume screen coordinates == physical
    pixels.' A transform between a monitor's logical (DPI-scaled,
    what UI Automation/pywinauto report) and physical (raw pixel, what a
    screenshot is captured in) coordinate spaces."""

    monitor_index: int
    dpi_scale: float = 1.0

    def logical_to_physical(self, rect: Rect) -> Rect:
        s = self.dpi_scale
        return Rect(
            left=round(rect.left * s),
            top=round(rect.top * s),
            width=round(rect.width * s),
            height=round(rect.height * s),
        )

    def physical_to_logical(self, rect: Rect) -> Rect:
        s = self.dpi_scale or 1.0
        return Rect(
            left=round(rect.left / s),
            top=round(rect.top / s),
            width=round(rect.width / s),
            height=round(rect.height / s),
        )


class TextRegion(BaseModel):
    """docs/phase-3/OCR.md §2 — one OCR-recognized word/line.
    'Do not assume OCR is always correct': `confidence` is always carried
    alongside the text, never dropped."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    bounds: Rect
    language: str = "eng"
    source: EvidenceTier = EvidenceTier.OCR


class VisualRegion(BaseModel):
    """docs/phase-3 §13 — a generic detected region, source-agnostic
    (OCR text block, vision-model detection, or a UIA element projected
    into screen space)."""

    label: str | None = None
    region_type: Literal["text", "icon", "button", "image", "control", "unknown"] = "unknown"
    bounds: Rect
    confidence: float = Field(ge=0.0, le=1.0)
    source: EvidenceTier


class SceneNode(BaseModel):
    """docs/phase-3/SCENE-GRAPH.md §2 — the platform-independent,
    normalized UI tree node a future AI planner actually consumes. Built
    from `computer_control`'s `UIElementNode` (raw UIA-shaped tree) via
    `from_ui_element_node`, never exposing the raw UIA structure directly
    (docs/phase-3 §7: 'never expose raw UIA structures to future AI
    agents')."""

    id: str = Field(default_factory=_new_id)
    automation_id: str | None = None
    name: str | None = None
    role: str | None = None
    class_name: str | None = None
    enabled: bool = True
    visible: bool = True
    bounds: Rect | None = None
    is_password: bool = False
    supported_patterns: list[str] = Field(default_factory=list)
    children: list[SceneNode] = Field(default_factory=list)

    @classmethod
    def from_ui_element_node(cls, node: UIElementNode) -> SceneNode:
        return cls(
            automation_id=node.automation_id,
            name=node.name,
            role=node.control_type,
            class_name=node.class_name,
            enabled=node.enabled,
            visible=node.visible,
            bounds=node.bounds,
            is_password=node.is_password,
            supported_patterns=list(node.supported_patterns),
            children=[cls.from_ui_element_node(child) for child in node.children],
        )

    def walk(self) -> list[SceneNode]:
        """Depth-first flattening — used by grounding/fusion so they can
        reason over a flat candidate list without re-implementing tree
        recursion at every call site."""
        result = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


SceneNode.model_rebuild()


class SceneGraph(BaseModel):
    """docs/phase-3/SCENE-GRAPH.md §1 — one window's normalized UI tree,
    plus provenance."""

    root: SceneNode
    window_handle: str | None = None
    window_title: str | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_id: str | None = None
    correlation_id: str | None = None
    source: ContentSource = ContentSource.UI_OBSERVATION


class GroundedElement(BaseModel):
    """docs/phase-3/PERCEPTION-FUSION.md §2 — a richer wrapper *around*
    SceneNode/VisualRegion produced by fusing same-element detections from
    multiple sources, not a replacement for either."""

    id: str = Field(default_factory=_new_id)
    name: str | None = None
    role: str | None = None
    text: str | None = None
    bounds: Rect | None = None
    visible: bool = True
    enabled: bool = True
    is_password: bool = False
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    sources: list[EvidenceTier] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_band: Confidence = Confidence.LOW
    source_content: ContentSource = ContentSource.UI_OBSERVATION


class TargetDescription(BaseModel):
    """docs/phase-3/VISUAL-GROUNDING.md §1 — what
    `GroundingEngine` is asked to find. At least one field must be given;
    enforced by `GroundingEngine`, not here, so a malformed request still
    round-trips as data (matching docs/phase-3 §41: observed/requested
    content is data, not something that short-circuits validation with an
    exception deep in a pydantic validator)."""

    text: str | None = None
    role: str | None = None
    name: str | None = None
    semantic_description: str | None = None
    window_title: str | None = None


GroundingStatus = Literal["GROUNDED", "AMBIGUOUS_TARGET", "NOT_FOUND"]


class GroundingResult(BaseModel):
    """docs/phase-3 §22 — mandatory ambiguity handling: on an ambiguous
    target, `status` is `AMBIGUOUS_TARGET` with `candidates` populated and
    `target` left None — the caller must never guess by picking
    `candidates[0]`."""

    status: GroundingStatus
    target: GroundedElement | None = None
    candidates: list[GroundedElement] = Field(default_factory=list)
    reason: str | None = None


class SceneChange(BaseModel):
    node: SceneNode
    change_type: Literal["added", "removed", "changed", "moved"]
    previous_bounds: Rect | None = None


class SceneDiff(BaseModel):
    """docs/phase-3/SCENE-DIFF.md — added/removed/changed/moved, computed
    by `vision.core.diff.compute_scene_diff`."""

    added: list[SceneNode] = Field(default_factory=list)
    removed: list[SceneNode] = Field(default_factory=list)
    changed: list[SceneChange] = Field(default_factory=list)
    moved: list[SceneChange] = Field(default_factory=list)
    before_captured_at: datetime | None = None
    after_captured_at: datetime | None = None

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed or self.moved)


class ScreenObservation(BaseModel):
    """docs/phase-3/SCREEN-OBSERVATION.md §1 — the top-level structured
    result of `screen.observe`. Never a raw screenshot in the primary
    record — `screenshot_ref` is an opaque handle into the short-lived
    in-memory cache (`vision.coordinator`), not embedded image bytes,
    matching docs/phase-3 §5/§30."""

    id: str = Field(default_factory=_new_id)
    window_handle: str | None = None
    window_title: str | None = None
    application_name: str | None = None
    scene: SceneGraph | None = None
    text_regions: list[TextRegion] = Field(default_factory=list)
    visual_regions: list[VisualRegion] = Field(default_factory=list)
    monitor: Monitor | None = None
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    source: ContentSource = ContentSource.UI_OBSERVATION
    screenshot_ref: str | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_id: str | None = None
    correlation_id: str | None = None
    stage_timings_ms: dict[str, int] = Field(default_factory=dict)
    sources_used: list[EvidenceTier] = Field(default_factory=list)


# --- docs/phase-3 §54: browser-agent preparation — interfaces only, not a
# full browser agent, and not duplicating Playwright/browser automation
# logic. Nothing in this phase constructs these; they exist so a future
# BrowserAgent (docs/architecture/06-BROWSER-CONTROL.md) has an agreed
# shape to target rather than inventing one from scratch. ---


class BrowserElement(BaseModel):
    tag: str
    role: str | None = None
    text: str | None = None
    bounds: Rect | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class BrowserScene(BaseModel):
    url: str
    title: str | None = None
    elements: list[BrowserElement] = Field(default_factory=list)


class DOMObservation(BaseModel):
    scene: BrowserScene
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: ContentSource = ContentSource.WEB_CONTENT
