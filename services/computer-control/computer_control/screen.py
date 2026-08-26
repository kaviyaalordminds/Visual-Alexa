"""Screen capture backend. Cross-platform via `mss` — see
docs/phase-2/SCREEN-CAPTURE.md. Verified against a real (virtual, Xvfb)
display in this environment; the underlying mechanism (mss) is identical
on Windows.

docs/security/05-DATA-PROTECTION.md / docs/phase-2 §14, §29: this module
never writes a capture to disk, never uploads it, and never calls any
network API. It returns image bytes to the caller and nothing else.
"""

from __future__ import annotations

import base64
import io

import mss
from PIL import Image
from veyra_contracts import ErrorCategory

from computer_control.core.backends import WindowBackend
from computer_control.core.models import Rect, ScreenCaptureResult


class WindowNotFoundForCaptureError(LookupError):
    def __init__(self, handle: str) -> None:
        super().__init__(f"No window found for handle '{handle}'.")
        self.code = ErrorCategory.WINDOW_NOT_FOUND


class NoActiveWindowError(LookupError):
    def __init__(self) -> None:
        super().__init__("No active window to capture.")
        self.code = ErrorCategory.WINDOW_NOT_FOUND


def _encode_png(raw_rgb: bytes, size: tuple[int, int]) -> str:
    image = Image.frombytes("RGB", size, raw_rgb)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _capture_region(bounds: Rect | None, display_index: int) -> ScreenCaptureResult:
    with mss.MSS() as sct:
        if bounds is not None:
            region = {
                "left": bounds.left,
                "top": bounds.top,
                "width": bounds.width,
                "height": bounds.height,
            }
        else:
            region = sct.monitors[display_index]
        shot = sct.grab(region)
        encoded = _encode_png(shot.rgb, shot.size)
        return ScreenCaptureResult(
            image_base64=encoded,
            width=shot.size[0],
            height=shot.size[1],
            display_index=display_index,
        )


class MssScreenBackend:
    """`window_backend` is optional so `capture_full` works with no
    dependency on window management at all (useful standalone, and on a
    non-Windows host where no real WindowBackend exists)."""

    def __init__(self, window_backend: WindowBackend | None = None) -> None:
        self._window_backend = window_backend

    async def capture_full(self) -> ScreenCaptureResult:
        # Monitor index 0 is the "all monitors combined" virtual screen in
        # mss; index 1 is the primary monitor — capture the primary.
        return _capture_region(bounds=None, display_index=1)

    async def capture_window(self, handle: str) -> ScreenCaptureResult:
        if self._window_backend is None:
            raise WindowNotFoundForCaptureError(handle)
        window = await self._window_backend.get_window(handle)
        if window is None or window.bounds is None:
            raise WindowNotFoundForCaptureError(handle)
        result = _capture_region(bounds=window.bounds, display_index=1)
        result.window_handle = handle
        return result

    async def capture_active_window(self) -> ScreenCaptureResult:
        if self._window_backend is None:
            raise NoActiveWindowError()
        window = await self._window_backend.get_active_window()
        if window is None or window.bounds is None:
            raise NoActiveWindowError()
        result = _capture_region(bounds=window.bounds, display_index=1)
        result.window_handle = window.handle
        return result

    async def capture_region(self, bounds: Rect, display_index: int = 1) -> ScreenCaptureResult:
        # docs/phase-3/SCREEN-OBSERVATION.md — an explicit sub-rectangle
        # capture, e.g. re-observing just a single grounded element's
        # bounds rather than the whole window/display.
        return _capture_region(bounds=bounds, display_index=display_index)
