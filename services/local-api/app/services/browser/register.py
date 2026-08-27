"""Assembles the Phase 8 browser tool context and registers every
`browser.*`/`web.research` tool into the existing (Phase 1) ToolRegistry —
called once at process startup, alongside Phase 2/3/7's own `register_*`
calls. See docs/phase-8/PHASE-8-IMPLEMENTATION-PLAN.md §6.

`browser_manager`/`observation_service`/`extension_bridge_service` are
process-wide singletons (manager.py/observation.py/extension_bridge.py),
the same pattern `tool_registry`/`integration_registry`/
`device_pairing_service` already established — `app/api/browser.py`
imports them directly rather than through this function.
"""

from __future__ import annotations

from app.services.browser.elements import ElementFusionEngine
from app.services.browser.manager import browser_manager
from app.services.browser.observation import observation_service
from app.services.browser.research import WebResearchAgent
from app.services.browser.security import (
    BrowserActionGuard,
    InstructionBoundary,
    SecretRedactor,
    URLValidator,
    WebContentSanitizer,
)
from app.services.browser.tools import BrowserToolContext, build_browser_tools
from app.services.browser.workflow import BrowserWorkflowEngine
from app.services.tool_registry import ToolRegistry


def register_browser_tools(registry: ToolRegistry) -> None:
    ctx = BrowserToolContext(
        manager=browser_manager,
        observation=observation_service,
        fusion=ElementFusionEngine(),
        url_validator=URLValidator(),
        sanitizer=WebContentSanitizer(),
        redactor=SecretRedactor(),
        boundary=InstructionBoundary(),
        guard=BrowserActionGuard(),
        research=WebResearchAgent(browser_manager),
        workflow=BrowserWorkflowEngine(),
        ocr_engine=_build_ocr_engine(),
    )
    for definition, executor in build_browser_tools(ctx):
        registry.register(definition, executor)  # type: ignore[arg-type]


def _build_ocr_engine():
    """Real tesseract-backed OCR (Phase 3's own engine) when the system
    binary is available; `None` otherwise so `ElementFusionEngine`'s
    vision fallback tier is honestly skipped rather than crashing at
    startup — mirrors `register_vision_tools`'s own optional-dependency
    handling."""
    try:
        from vision.ocr.engine import OCREngine

        return OCREngine()
    except ImportError:  # pragma: no cover - vision is a declared dependency
        return None
