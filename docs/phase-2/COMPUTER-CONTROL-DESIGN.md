# Computer-Control Engine Design

## 1. Where it lives

```
services/computer-control/          # new installable Python package,
  computer_control/                 # imported by services/local-api —
    core/                           # NOT a second running process
      models.py        # ApplicationInfo, WindowInfo, ProcessInfo,
                        #   UIElementInfo, InputTarget, InputContext,
                        #   ScreenCaptureResult, Rect
      selectors.py      # UISelector — the one, fixed selector language
      results.py         # ActionResult, ActionStatus, VerificationOutcome
      backends.py          # Protocol interfaces every backend implements
      capabilities.py        # sys.platform-based capability detection
      waiting.py               # wait_for_element (polling + timeout)
    windows/            # real Windows backends (pywinauto/pywin32),
                        #   every OS import lazy — see §2
    filesystem/          # cross-platform: FilesystemEngine + PathPolicy
    testing/               # fake backends, same interfaces as windows/
    processes.py             # PsutilProcessBackend (cross-platform)
    screen.py                  # MssScreenBackend (cross-platform)
    launcher.py                  # filesystem.open's platform dispatch
    registry.py                    # ApplicationRegistry (resolver)

services/local-api/app/services/computer_control/
    backends.py          # build_backend_bundle(): picks real vs. None
                        #   per capability, at process startup
    support.py            # callable_executor: shared result/error
                        #   mapping + the computer_control.enabled gate
    application_tools.py, window_tools.py, filesystem_tools.py,
    input_tools.py, screen_tools.py, ui_tools.py   # ToolDefinition +
                        #   executor per capability domain
    register.py           # wires all of the above into the existing
                        #   (Phase 1) ToolRegistry
```

Why a library package consumed by the existing Local API process, rather
than the brief's suggested standalone `computer-control/` service: Phase 1
already established "one Local API, one Tool Registry, one Policy Engine"
as a non-negotiable (`CLAUDE.md`). A second process would mean either a
second tool-execution/audit path (duplicating the security-critical
Policy Engine) or an RPC hop with its own trust boundary to design. Neither
is justified for Phase 2's scope — see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §3.

## 2. The platform-capability split

`computer_control.core` is pure data models, selectors, and `Protocol`
interfaces — no OS dependency, imports and runs identically on any host.
`computer_control.windows` contains the real implementations, but every
Windows-only import (`pywinauto`, `pywin32`/`win32gui`) is inside a
function or method body, never at module top level. This means:

- The package **installs** on Linux (this development environment)
  without `pywinauto`/`pywin32` present at all — they're declared as
  `sys_platform == 'win32'`-conditional dependencies in
  `services/computer-control/pyproject.toml`.
- The **module** `computer_control.windows.applications` (etc.) **imports
  cleanly** on Linux — verified directly: `import computer_control.windows.applications`
  succeeds here (see the Phase 2 report for the exact command run).
- **Calling** a method on a real Windows backend on a non-Windows host
  would raise `ImportError` deep inside — but this never happens, because
  `app/services/computer_control/backends.py`'s `build_backend_bundle()`
  only ever constructs a real Windows backend when
  `computer_control.core.capabilities.detect_capabilities().is_windows`
  is `True`. Everywhere else, the corresponding backend field is `None`,
  and every tool built against it uses `platform_unsupported_executor`
  instead, which fails with a structured `PLATFORM_NOT_SUPPORTED` error —
  never a crash, never silent success.

Two capabilities are **not** platform-gated at all, because they are
genuinely cross-platform: process listing (`psutil`) and screen capture
(`mss`). Both are exercised for real in this development environment.

## 3. The umbrella `computer_control.enabled` gate

Phase 1 seeded a `computer_control.enabled` system setting (default
`False`) and showed it on the status screen, but nothing checked it — no
computer-control tool existed yet. Phase 2 completes that: every tool
built through `app/services/computer_control/support.py`'s
`callable_executor` checks this setting before doing anything else,
mirroring `CLAUDE.md`'s "microphone, screen capture, external devices,
and remote access are OFF by default... no exceptions" — computer control
itself now belongs in that list. `screen.capture` additionally checks the
more specific `screen_observation.enabled` setting, layered on top.

## 4. The one execution path (brief §41, verified)

There is no separate "developer" vs. "AI" code path. The desktop shell's
developer console (`apps/desktop/src/DevConsole.tsx`) calls
`POST /tools/{id}/invoke`, exactly the same HTTP endpoint any future AI
planner would call, which resolves to exactly the same
`execute_tool_call` → Policy Engine → `ToolRegistry.get_executor` →
`callable_executor` chain every other tool call in this codebase takes.
There is no shortcut, no internal-only invocation path, nothing that
bypasses the Policy Engine for "trusted" callers.

## 5. What was verified in this environment vs. what wasn't

See `docs/phase-2/PHASE-2-TEST-RESULTS.md` for the full breakdown. In
short: filesystem, screen capture, path security, the Tool Registry/Policy
Engine integration, and every orchestration behavior (verification
structure, error mapping, `TARGET_CONTEXT_REQUIRED`, the enable gates) are
verified for real, including through the actual desktop shell UI via a
live server. The real Windows backends (`computer_control.windows.*`) are
verified to import cleanly and are believed correct against the
documented `pywinauto`/`pywin32` APIs, but their actual runtime behavior
against a real Windows Notepad/Explorer/etc. is **not** verified — this
container has no Windows kernel to run them against.
