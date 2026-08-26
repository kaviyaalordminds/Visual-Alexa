"""Platform-independent data models for the computer-control engine.
docs/phase-2/COMPUTER-CONTROL-DESIGN.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Rect(BaseModel):
    left: int
    top: int
    width: int
    height: int


ApplicationState = Literal["running", "not_running", "unknown"]


class ApplicationInfo(BaseModel):
    """docs/phase-2/APPLICATION-CONTROL.md §6.1 — deliberately excludes
    command-line arguments and full executable path from the *default*
    serialized form exposed to callers beyond what's needed to identify
    the app, per the brief's 'do not expose unnecessary sensitive
    information.'"""

    name: str
    process_id: int
    window_title: str | None = None
    state: ApplicationState = "running"


class ProcessInfo(BaseModel):
    pid: int
    name: str
    parent_pid: int | None = None
    cpu_percent: float | None = None
    memory_mb: float | None = None


class WindowInfo(BaseModel):
    # Opaque, backend-specific handle (e.g. an HWND rendered as a string).
    # Never a raw coordinate — see docs/phase-2/WINDOW-CONTROL.md.
    handle: str
    title: str
    process_id: int
    is_active: bool = False
    is_minimized: bool = False
    is_maximized: bool = False
    bounds: Rect | None = None


class UIElementInfo(BaseModel):
    """docs/phase-2/WINDOWS-UI-AUTOMATION.md §11."""

    automation_id: str | None = None
    name: str | None = None
    control_type: str | None = None
    class_name: str | None = None
    enabled: bool = True
    visible: bool = True
    bounds: Rect | None = None
    supported_patterns: list[str] = Field(default_factory=list)


class InputContext(BaseModel):
    """docs/phase-2 §23, §16 — every keyboard/mouse/UI operation carries
    this; TARGET_CONTEXT_REQUIRED is returned when it's missing rather than
    guessing a target."""

    task_id: str | None = None
    step_id: str | None = None
    correlation_id: str
    user_id: str
    permission_context: str | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW"] | None = None


class InputTarget(BaseModel):
    """docs/phase-2 §16 — identifies exactly which window/element an
    input operation applies to. Never implicit/global. Construction fails
    (ValidationError, mapped by the tool executor layer to
    TARGET_CONTEXT_REQUIRED) if no target is identified at all — 'DO NOT
    EXECUTE' is enforced structurally, not by convention."""

    window_handle: str | None = None
    window_title: str | None = None
    element_automation_id: str | None = None

    @model_validator(mode="after")
    def _requires_a_target(self) -> InputTarget:
        if self.is_empty():
            raise ValueError(
                "InputTarget requires window_handle or window_title — "
                "docs/phase-2 §16: TARGET_CONTEXT_REQUIRED."
            )
        return self

    def is_empty(self) -> bool:
        return not (self.window_handle or self.window_title or self.element_automation_id)


class ScreenCaptureResult(BaseModel):
    """docs/phase-2/SCREEN-CAPTURE.md — image bytes are returned as base64
    PNG, kept in memory / the API response only; never written to disk or
    uploaded anywhere by this engine (docs/security/05-DATA-PROTECTION.md)."""

    image_base64: str
    width: int
    height: int
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    display_index: int | None = None
    window_handle: str | None = None
