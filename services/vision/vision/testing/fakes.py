"""Fake perception backends — deterministic, no OS/model dependency.
Mirrors computer_control.testing's fake-backend pattern
(docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §2).
"""

from __future__ import annotations

from vision.core.models import TargetDescription, VisualRegion
from vision.core.vision_provider import VisionAnalysisResult


class FakeVisionProvider:
    """Implements the same `VisionProvider` Protocol as
    `NotConfiguredVisionProvider`, but returns seeded, deterministic
    results — used to test the parts of the pipeline (fusion, the
    ObservationCoordinator's last-resort tier) that only run when a
    vision provider *is* configured, without needing a real model."""

    def __init__(self) -> None:
        self.regions: list[VisualRegion] = []
        self.description: str | None = "A fake described scene."

    def seed_region(self, region: VisualRegion) -> None:
        self.regions.append(region)

    async def analyze_image(self, image_base64: str, prompt: str) -> VisionAnalysisResult:
        return VisionAnalysisResult(
            available=True, description=self.description, regions=self.regions
        )

    async def detect_elements(self, image_base64: str) -> list[VisualRegion]:
        return list(self.regions)

    async def describe_scene(self, image_base64: str) -> VisionAnalysisResult:
        return VisionAnalysisResult(
            available=True, description=self.description, regions=self.regions
        )

    async def locate_target(
        self, image_base64: str, target: TargetDescription
    ) -> list[VisualRegion]:
        needle = (target.text or target.name or target.semantic_description or "").lower()
        if not needle:
            return list(self.regions)
        return [r for r in self.regions if r.label and needle in r.label.lower()]


class FakeDpiProvider:
    """Stands in for `vision.windows.dpi.get_dpi_scale_for_window` in
    tests, since the real one requires Windows."""

    def __init__(self, scales_by_handle: dict[str, float] | None = None) -> None:
        self._scales = scales_by_handle or {}

    def get_dpi_scale_for_window(self, window_handle: str) -> float:
        return self._scales.get(window_handle, 1.0)


class FakeUITreeProvider:
    """Stands in for `vision.windows.ui_tree.capture_scene_graph`'s
    Windows-only real path — tests instead drive
    `computer_control.testing.FakeUIAutomationBackend.seed_tree` and call
    `capture_scene_graph` directly against the fake backend, since that
    function is itself already backend-agnostic (see
    vision/windows/ui_tree.py's module docstring). This class exists for
    the rarer case a test wants to bypass the backend entirely."""

    def __init__(self, scene_graph: object | None = None) -> None:
        self.scene_graph = scene_graph
