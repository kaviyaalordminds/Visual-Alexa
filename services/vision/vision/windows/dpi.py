"""Windows-only DPI/monitor-scaling query. docs/phase-3/UI-TREE.md §5,
docs/phase-3/PERFORMANCE.md (DPI test).

Real code, reviewed but NOT runtime-verified in this Linux environment —
see docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §2. Every ctypes/win32
access is lazy-imported inside a function body, identical discipline to
`computer_control.windows` (docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md
§4), so this module still imports cleanly on non-Windows hosts.

Monitor *layout* (position/size, monitor count) is genuinely cross-platform
and is handled separately in `vision.coordinator` via `mss` — this module
supplies only the Windows-specific *scale factor* on top of that layout.
"""

from __future__ import annotations


class DpiUnavailableError(RuntimeError):
    """docs/phase-3 §12 — never silently assume 100% scaling on a host
    where the real DPI is knowable but the query failed; callers must
    handle this explicitly (e.g. fall back to `dpi_scale=1.0` with that
    fact recorded, not hidden)."""


def get_dpi_scale_for_window(window_handle: str) -> float:
    """Returns the DPI scale factor (1.0 = 100%, 1.5 = 150%, 2.0 = 200%)
    Windows is applying to the monitor the given window is on, via
    `GetDpiForWindow` (Windows 10 1607+). `window_handle` is the same
    opaque HWND-as-string `WindowInfo.handle` already uses elsewhere in
    this codebase."""
    import ctypes

    try:
        hwnd = int(window_handle)
    except ValueError as exc:
        raise DpiUnavailableError(f"'{window_handle}' is not a numeric HWND.") from exc
    try:
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)  # type: ignore[attr-defined]
    except (AttributeError, OSError) as exc:
        raise DpiUnavailableError(str(exc)) from exc
    if not dpi:
        raise DpiUnavailableError(f"GetDpiForWindow returned 0 for handle '{window_handle}'.")
    # 96 DPI is Windows' documented 100% baseline.
    return dpi / 96.0
