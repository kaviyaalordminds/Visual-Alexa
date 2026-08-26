# Window Control

## Semantic identification, never coordinates

Every `window.*` tool identifies its target by an opaque `handle` string
(the real backend's HWND rendered as text) or a `title_query` substring —
never an x/y screen position. `window.get_bounds` *returns* a rectangle
(useful for e.g. scoping a screen capture) but no tool *accepts* one as an
input to act on.

## Tools and risk tiers

| Tool | Risk | Why |
|---|---|---|
| `window.list`, `window.find`, `window.get_active`, `window.get_bounds`, `window.get_title` | SAFE | Read-only. |
| `window.focus`, `window.minimize`, `window.maximize`, `window.restore` | SAFE | Cosmetic, fully reversible — matches the brief's own "open application" SAFE example. |
| `window.close` | MODERATE | Same reasoning as `application.close`. |

## Verification

Every state-changing tool (`focus`/`minimize`/`maximize`/`close`) re-reads
the window's state after acting and only reports `VERIFIED` when the
expected flag (`is_active`/`is_minimized`/`is_maximized`, or the window's
absence for `close`) actually changed — see
`app/services/computer_control/window_tools.py`'s `_state_action` helper,
shared by all four so the verification behavior can't drift between them.
`window.restore` verifies only that the call succeeded (no single
"is_restored" flag exists to check against) — documented as a narrower
verification than the others, not silently skipped.

## Real backend vs. what's tested here

`computer_control.windows.windows_ctl.WindowsWindowBackend` uses
`pywinauto.Desktop(backend="uia")` for enumeration/control and
`win32gui.GetForegroundWindow()` for `get_active_window` — real, reviewed
Windows code, not runtime-verified in this Linux container (see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2).
`computer_control.testing.FakeWindowBackend` implements the identical
`WindowBackend` Protocol with deterministic in-memory state, and
`tests/integration/test_fake_backed_computer_control.py` drives the full
focus → minimize → close → re-list round trip through the real HTTP API
against it, proving the orchestration (Policy Engine tiers, verification
logic, `WINDOW_NOT_FOUND` error mapping) is correct independent of which
concrete backend is behind it.
