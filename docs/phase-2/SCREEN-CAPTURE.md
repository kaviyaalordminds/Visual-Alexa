# Screen Capture

## Two independent gates, both required

1. **`screen_observation.enabled`** system setting — Phase 1 seeded this
   `False` with nothing checking it; Phase 2's `screen_tools.py` is the
   first code to actually check it. Verified:
   `tests/integration/test_screen_tools_api.py::test_screen_capture_denied_when_observation_setting_is_off_by_default`.
2. **`computer_control.enabled`** — the Phase 2 umbrella gate (see
   `docs/phase-2/COMPUTER-CONTROL-DESIGN.md` §3), checked first.
3. A normal Policy Engine `PermissionGrant` (MODERATE tier) is *also*
   still required — three independent checks, not one.

## Local-only, by construction

`computer_control.screen.MssScreenBackend` uses the `mss` library, reads
pixels via `sct.grab()`, encodes to PNG in memory (`PIL.Image` +
`io.BytesIO`), and returns base64 bytes in the HTTP response. There is no
disk write, no network call, no upload anywhere in this module — grep
confirms it (and `tests/security/test_no_unrestricted_shell.py`'s broader
sweep would catch any `subprocess`/network-primitive addition regardless).
Nothing is persisted between captures; each call is independent.

## Genuinely verified, not just unit-tested

Screen capture was proven end-to-end against a **real (virtual) X display**
in this environment: `Xvfb` was started, the Local API was pointed at it
via `DISPLAY`, and `screen.capture` was invoked through the real HTTP API
and — separately — through the actual desktop shell's developer console
in a real browser (Playwright), returning a real 640×480 (API test) /
live-window-sized (UI test) PNG each time. See
`tests/integration/test_screen_tools_api.py::test_screen_capture_succeeds_with_both_gates_satisfied`
(skipped automatically when no `DISPLAY` is present, so CI without a
display doesn't fail) and the Phase 2 report for the exact screenshots
captured during manual verification.

## Window-scoped capture

`capture_window(handle)` / `capture_active_window()` resolve the target
window's bounds via an injected `WindowBackend` (optional — `capture_full`
works with none at all) and crop the capture region accordingly; both
raise a structured `WINDOW_NOT_FOUND` error (not a blank image) when no
window backend is available or the window doesn't exist.

## Risk tier

MODERATE for all three tools — not SAFE, because a capture can contain
sensitive on-screen content; not SENSITIVE/CRITICAL, because the content
never leaves the local machine (docs/phase-2 §14, §29).
