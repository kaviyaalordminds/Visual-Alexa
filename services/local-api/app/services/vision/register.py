"""Registers every Phase 3 visual-perception tool into the existing
(Phase 1) ToolRegistry — called once at process startup, right after
Phase 2's `register_computer_control_tools`. See
docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §6.
"""

from __future__ import annotations

from vision.core.vision_provider import NotConfiguredVisionProvider, VisionProvider
from vision.ocr.engine import OCREngine

from app.services.computer_control.backends import BackendBundle
from app.services.tool_registry import ToolRegistry
from app.services.vision.backends import build_observation_coordinator
from app.services.vision.tools import build_vision_tools


def register_vision_tools(
    registry: ToolRegistry,
    bundle: BackendBundle,
    *,
    ocr_engine: OCREngine | None = None,
    vision_provider: VisionProvider | None = None,
) -> None:
    """`ocr_engine`/`vision_provider` are normally left as None, resolving
    the real (tesseract-backed) engine and the `NotConfiguredVisionProvider`
    stub — the test suite passes fakes instead, mirroring
    `register_computer_control_tools`'s `bundle` override
    (docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2)."""
    ocr_engine = ocr_engine or OCREngine()
    vision_provider = vision_provider or NotConfiguredVisionProvider()
    coordinator = build_observation_coordinator(bundle)
    coordinator.ocr_engine = ocr_engine
    coordinator.vision_provider = vision_provider

    tools = build_vision_tools(bundle, coordinator, ocr_engine, vision_provider)
    for definition, executor in tools:
        registry.register(definition, executor)  # type: ignore[arg-type]
