"""Provider-independent vision-model abstraction. docs/phase-3/VISION-PROVIDER.md.

No real provider ships in Phase 3 (docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md
§4) — this module defines only the `Protocol` a future local model or
cloud provider (OpenAI/Anthropic-compatible/Gemini/local) must implement,
plus `NotConfiguredVisionProvider`, the one implementation Phase 3 ships,
mirroring Phase 1's 'AI: NOT CONFIGURED' status pattern.

CLAUDE.md / docs/phase-3 §16-17: a *cloud* provider must pass
Policy -> Privacy Check -> Config -> Redaction -> Provider, and must never
auto-enable — enforced by `app/services/vision` in the local-api tool
layer, not here (this module has no network access at all).
"""

from __future__ import annotations

from typing import Protocol

from vision.core.models import TargetDescription, VisualRegion


class VisionAnalysisResult:
    """Plain result container rather than a pydantic model — this type is
    never serialized directly into a tool result on its own; a caller maps
    it into `ScreenObservation`/`GroundedElement` fields."""

    def __init__(
        self,
        *,
        available: bool,
        description: str | None = None,
        regions: list[VisualRegion] | None = None,
        reason: str | None = None,
    ) -> None:
        self.available = available
        self.description = description
        self.regions = regions or []
        self.reason = reason


class VisionProvider(Protocol):
    """docs/phase-3 §15 — every method returns a result rather than
    raising when vision simply isn't available, so callers (the
    `ObservationCoordinator`) can treat 'no vision configured' as an
    ordinary, expected outcome instead of an exceptional one."""

    async def analyze_image(self, image_base64: str, prompt: str) -> VisionAnalysisResult: ...
    async def detect_elements(self, image_base64: str) -> list[VisualRegion]: ...
    async def describe_scene(self, image_base64: str) -> VisionAnalysisResult: ...
    async def locate_target(
        self, image_base64: str, target: TargetDescription
    ) -> list[VisualRegion]: ...


class NotConfiguredVisionProvider:
    """The only `VisionProvider` Phase 3 ships. Every method returns a
    structured 'vision unavailable' result — never raises, never fabricates
    a detection. The `ObservationCoordinator` is designed so UIA + OCR +
    metadata alone already answer the large majority of grounding
    questions without ever calling this (docs/phase-3
    /PHASE-3-IMPLEMENTATION-PLAN.md §4)."""

    async def analyze_image(self, image_base64: str, prompt: str) -> VisionAnalysisResult:
        return VisionAnalysisResult(available=False, reason="No vision provider configured.")

    async def detect_elements(self, image_base64: str) -> list[VisualRegion]:
        return []

    async def describe_scene(self, image_base64: str) -> VisionAnalysisResult:
        return VisionAnalysisResult(available=False, reason="No vision provider configured.")

    async def locate_target(
        self, image_base64: str, target: TargetDescription
    ) -> list[VisualRegion]:
        return []
