# Window Perception

Phase 3 does not reimplement window detection. `ObservationCoordinator`
takes Phase 2's `WindowBackend` (`computer_control.core.backends.WindowBackend`)
directly and calls `get_window`/`get_active_window` to resolve which
window an observation or grounding request applies to
(`vision/coordinator.py::observe`). The existing `window.*` tools
(`window.list`, `window.get_active`, `window.focus`, ...) are unchanged
and are the only way to enumerate or control windows — Phase 3 adds no
parallel `screen.get_active_window` tool, per
`PHASE-3-IMPLEMENTATION-PLAN.md` §6.

A `ScreenObservation`'s `window_handle`/`window_title` fields are filled
from the resolved `WindowInfo` when a `WindowBackend` is available;
otherwise they fall back to whatever the caller passed in, so a
`window=None` (fake or Windows-only-unavailable) host degrades honestly
rather than fabricating a window identity.
