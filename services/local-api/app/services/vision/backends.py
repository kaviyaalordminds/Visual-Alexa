"""Constructs the `ObservationCoordinator` this process will use, from the
same `BackendBundle` Phase 2 already built via real platform-capability
detection — never a second, parallel capability-detection path.
docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §3.
"""

from __future__ import annotations

from vision.coordinator import ObservationCoordinator
from vision.core.vision_provider import NotConfiguredVisionProvider
from vision.ocr.engine import OCREngine

from app.services.computer_control.backends import BackendBundle


def build_observation_coordinator(bundle: BackendBundle) -> ObservationCoordinator:
    return ObservationCoordinator(
        screen=bundle.screen,
        ui_automation=bundle.ui_automation,
        window=bundle.window,
        ocr_engine=OCREngine(),
        # docs/phase-3/VISION-PROVIDER.md — the only provider Phase 3
        # ships; a future phase swaps this for a real local/cloud provider
        # behind the same Protocol, gated per docs/phase-3 §16-17.
        vision_provider=NotConfiguredVisionProvider(),
    )
