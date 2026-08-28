# Computer Control Subsystem Status

**Current status in this environment: NOT ENABLED** (default) —
`computer_control.enabled` permission flag is off. If manually enabled on
this Linux sandbox, the real answer becomes **DISABLED** ("Windows UI
Automation backends are unavailable on this platform — Computer Control
requires Windows"), never a fake CONNECTED — confirmed live this
activation by flipping the flag and re-checking `/system`.

## Architecture (already real, activation only added the health check)

```
AI -> Planner -> Tool Request -> Policy Engine -> Permission Engine -> Computer Control -> Windows -> Verification
```

`services/computer-control/computer_control/windows/` has real Win32/UI
Automation backends (`applications.py`, `keyboard.py`, `mouse.py`,
`ui_automation.py`, `windows_ctl.py`), gated by
`computer_control.core.capabilities.detect_capabilities()` (`is_windows =
sys.platform == "win32"`). On non-Windows, real backends are never even
constructed — tool calls honestly report platform-unsupported, they never
fake success. This was already true before this activation; what's new is
that `/system` now reflects it accurately instead of reporting CONNECTED
whenever the permission flag alone was on.

## The three real conditions for CONNECTED

`compute_computer_control_status()` (`app/services/subsystem_health.py`)
requires all of:

1. `computer_control.enabled` permission flag is on (an explicit user
   action — never on by default).
2. The real platform check (`sys.platform == "win32"`) passes.
3. (Implicitly, by construction) the Policy Engine is active — it always
   is; there is no path to disable it.

Only then: `CONNECTED`. Missing (1): `NOT ENABLED`. (1) true but (2)
false: `DISABLED`, with the platform named in the reason.

## Evidence-tier priority (unchanged, already correct)

Native Windows API → UI Automation → Application APIs → Accessibility →
Browser DOM → Keyboard/mouse → coordinate-based clicking as an explicit
last resort never used as primary. Confirmed real in
`docs/PHASE-9-AUDIT.md` — this activation touched only the status
reporting layer, not the automation logic itself.

## Safe tests (already implemented, Phase 2)

"Open Notepad"/"Open Calculator" (application-launch tools, resolved
through `ApplicationRegistry`'s allowlisted `executable_candidates`),
"Create a folder called VEYRA-Test" (filesystem tools, validated through
`PathValidator`). All already exist and are already tested — no new tool
was needed for this activation.

## On a real Windows machine

With `computer_control.enabled=true` and the app running on Windows,
`detect_capabilities().is_windows` is `True`, real backends construct
successfully, and `/system` reports genuine `CONNECTED` — this was
already the architecture's design; this activation only made the
*reporting* honest, it didn't change the underlying Windows automation
code at all.
