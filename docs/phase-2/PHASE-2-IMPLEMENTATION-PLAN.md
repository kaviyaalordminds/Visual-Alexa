# Phase 2 Implementation Plan — Local Windows Computer-Control Engine

Written before substantial implementation, per the Phase 2 brief §0. This
document records what Phase 1 actually built (not just what was planned),
where Phase 2's suggested design conflicts with it, the adaptation decided
in each case, and the technology choices with rationale.

## 1. What Phase 1 actually implemented (repository inspection findings)

Verified by reading `CLAUDE.md`, `docs/architecture/*`, `docs/security/*`,
and the actual code in `packages/contracts` and `services/local-api`:

- **One process owns everything.** `services/local-api` (FastAPI) is the
  only process with database access and the only process that invokes a
  tool, exactly as `docs/architecture/01-SYSTEM-ARCHITECTURE.md` specifies.
  There is no separate "computer-control service" process in Phase 1 — the
  Tool Registry, Policy Engine, and Tool Executors all live inside the
  Local API's process.
- **`ToolRegistry`** (`services/local-api/app/services/tool_registry.py`)
  is a simple in-process singleton: `register(definition, executor)`,
  `get`, `get_executor`, `list`. Definitions are `veyra_contracts.ToolDefinition`
  Pydantic models; executors implement the `ToolExecutor` protocol
  (`async def execute(call) -> ToolResult`).
- **`PolicyEngine`** (`services/local-api/app/services/policy_engine.py`)
  is the single enforcement point: SAFE always allowed, CRITICAL always
  requires a fresh `PermissionRequest` (no stored grant ever satisfies it),
  MODERATE/SENSITIVE require a valid unexpired unrevoked `PermissionGrant`
  matching `(user, tool_id, target-or-None)`.
- **`execute_tool_call`** (`services/local-api/app/services/tool_execution.py`)
  is the one orchestration path every tool call takes: resolve definition →
  policy check → executor → audit log (always, success or failure) → event
  publish. This is the exact chain Phase 2 must plug into, unchanged.
- **Contracts** (`packages/contracts/python/veyra_contracts`) define
  `RiskLevel`, `ToolCategory` (already includes `filesystem`, `windows`,
  `process`, `screen`, `keyboard`, `mouse` — Phase 1 anticipated Phase 2's
  categories), `ErrorCategory`, `EvidenceTier`, `TaskState` + legal
  transitions, `PermissionGrant`/`PermissionRequest`, `ToolDefinition`/
  `ToolCallRequest`/`ToolResult`.
- **Database**: SQLAlchemy models + Alembic migrations
  (`services/local-api/app/models`, `database/migrations`). An
  `applications` table already exists (`app/models/application.py`) with
  `name`, `executable_path`, `identifier` — a partial Application Registry
  Phase 2 extends rather than replaces.
- **Only one real tool exists**: `system.get_status` (SAFE, read-only). No
  filesystem/window/UI/keyboard/mouse/screen tool exists yet — Phase 2 is
  genuinely greenfield for all of §6–§16 of the brief.
- **API surface**: `/tools`, `/tools/{id}/invoke`, `/permissions`,
  `/memory`, `/devices`, `/tasks`, `/settings`, `/system`, `/health`,
  `/events` (WebSocket). No new top-level routes are needed for Phase 2 —
  new tools are exposed through the existing `/tools` surface.
- **Desktop shell**: Tauri + React, currently a static status screen
  (`apps/desktop/src/App.tsx`) polling `/system`. No developer panel exists.
- **Environment**: this development/build/test container is **Linux**
  (Ubuntu 24.04), not Windows. Phase 1's desktop shell doc already
  documents this constraint and how it was handled (Tauri chosen partly
  *because* it's buildable here; the shell was verified launching under
  Xvfb, not on real Windows). Phase 2 inherits the same constraint, sharper:
  most of §4–§16 of the brief (Win32 APIs, UI Automation, real window
  management) has **no meaningful equivalent on Linux** — there is no
  Windows kernel, no `user32.dll`, no `UIAutomationCore.dll` here.

## 2. The central adaptation this phase requires

**Phase 2's target functionality only exists on Windows. This build
environment is Linux.** Phase 1 handled an analogous gap (no display
server) by being explicit about what was and wasn't verified rather than
pretending success. Phase 2 needs the same discipline, applied more
broadly:

- Every Windows-specific backend (application launch/focus, window
  management, UI Automation, keyboard/mouse targeting) is written as
  **real, correct Windows implementation code** — not a mock, not a
  TODO — using established, well-maintained Windows automation libraries.
  It is **not runtime-executable or testable in this container**, because
  the OS APIs it calls do not exist here. This is stated plainly in every
  relevant doc and in the final report, not glossed over.
- Everything that is **not** inherently OS-specific — the filesystem
  engine and path security, the Tool Registry/Policy Engine integration,
  the selector-resolution and retry/timeout logic, the verification
  result model, the error model, audit redaction, screen capture — **is
  built and genuinely tested in this environment**, including against a
  real (virtual) display via the same Xvfb approach Phase 1 validated the
  desktop shell with.
- A **fake/test-double backend** (`computer_control.testing`) implements
  the exact same backend interfaces as the real Windows backend. Tests
  exercise the full Policy→Registry→Executor→Verify→Audit pipeline against
  the fakes, proving the *orchestration and security logic* is correct
  independent of the concrete OS backend. This is standard practice for
  platform-specific systems (the same reason Phase 1 kept controller
  *interfaces* separate from implementations in `docs/architecture/05-COMPUTER-CONTROL.md`)
  and is not a shortcut — it's the only way to make the security-critical
  parts of this phase (path validation, permission enforcement, target-
  context requirements) verifiable at all in this container.
- Tools are registered identically on every platform (so `/tools` and the
  OpenAPI schema are platform-independent), but the **executor** selected
  at process startup depends on `sys.platform`: real Windows backend when
  `sys.platform == "win32"`, otherwise a `PlatformUnsupportedExecutor` that
  fails safely with a new `PLATFORM_NOT_SUPPORTED` error rather than
  crashing, silently no-op'ing, or pretending to succeed.

## 3. Structural adaptation: `computer-control/` placement

The brief suggests a top-level `computer-control/` directory. Per
`CLAUDE.md`'s "never duplicate services — one Local API, one... tool
registry, one policy engine," this is implemented as a **library package
consumed by the existing Local API process**, not a second service:

```
services/computer-control/          # new installable Python package
  pyproject.toml                    # "veyra-computer-control"
  computer_control/
    core/            # platform-independent: models, selectors, results,
                      #   errors, verification, capabilities, backend
                      #   Protocol interfaces — importable/testable anywhere
    windows/          # real Windows backends (pywinauto/psutil/mss-based);
                      #   guarded by sys.platform, not imported elsewhere
    filesystem/         # cross-platform filesystem engine + path security
                      #   (genuinely platform-independent — Windows-specific
                      #   protected-path *data*, not platform-specific code)
    testing/              # fake backends implementing the same interfaces,
                      #   used by services/local-api's test suite
    registry.py             # ApplicationRegistry (resolver)
services/local-api/app/services/
  computer_control_tools.py   # registers Phase 2 ToolDefinitions +
                      #   platform-appropriate executors into the existing
                      #   ToolRegistry at startup, alongside bootstrap.py
```

This mirrors the `packages/contracts` pattern already established (a
pip-installable local package, editable-installed alongside `local-api`)
rather than inventing a new integration mechanism.

## 4. Technology decisions

| Need | Candidates | Decision | Why |
|---|---|---|---|
| Window/UI Automation control | raw `comtypes`+UIAutomationCore, `pywinauto`, PyAutoGUI | **`pywinauto`** (Windows-only dependency, imported lazily) | Wraps both Win32 (`win32` backend) and UI Automation (`uia` backend) behind one well-maintained, BSD-licensed library; element-bound `.click()`/`.type_keys()` matches the brief's "target-first, coordinates last" requirement directly, rather than hand-rolling raw COM bindings untested in this environment. Explicitly not PyAutoGUI — brief §4 forbids it as the core mechanism; PyAutoGUI is coordinate-only with no semantic element model. |
| Process listing | `pywin32` only, `psutil` | **`psutil`** | Cross-platform, mature, MIT-licensed, does not require a Windows-only dependency for the parts of process inspection (PID, name, memory, CPU) that don't need Win32; this also means process-listing logic is genuinely testable in this Linux container. Window-title/handle association still requires the Windows backend. |
| Screen capture | `PIL.ImageGrab`, `pyautogui.screenshot`, `mss` | **`mss`** | Cross-platform (Windows/Linux/macOS), fast, MIT-licensed, no GUI-automation baggage (doesn't pull in coordinate-clicking APIs the way PyAutoGUI would). Verified working against a real Xvfb display in this environment. |
| Application launch | `os.startfile` (Windows-only), `subprocess.Popen([...])` | **`subprocess.Popen([executable_path, *args], shell=False)`** | List-argv, `shell=False` (the default) — never a shell string. This is the one place Phase 1's blanket "no `subprocess.`" security test needed narrowing; see §5. |

No dependency was added "to make a demo easier" — each solves a specific
capability the brief requires and has no simpler standard-library
equivalent (the standard library has no UI Automation or cross-platform
screenshot capability).

## 5. Conflict identified: Phase 1's security test bans all `subprocess.` usage

`tests/security/test_no_unrestricted_shell.py` currently fails the build
on *any* occurrence of the substring `subprocess.` anywhere in application
code. That test was written for Phase 1, when no tool needed to spawn a
process at all. Phase 2's `application.launch` legitimately *must* spawn a
process for a resolved, allow-listed executable — that is what "open
Notepad" means at the OS level, and the brief's own §19 explicitly
endorses "a specific strongly typed tool" that does this, contrasting it
with a generic `system.execute("whatever")`.

**Resolution**: narrow the test so it still bans everything it was built to
ban — `shell=True`, `os.system(`, `os.popen(`, PowerShell/`Invoke-Expression`
— while permitting `subprocess.Popen`/`subprocess.run` calls, **and add a
new, more precise security test** that statically asserts every such call
site passes a **list literal**, never an f-string/`.format()`/string
concatenation, as the command argument, with `shell` never set to `True`.
This is a strictly stronger guarantee than the blanket ban: it directly
tests the property that actually matters (no shell interpretation, no
string-built commands) instead of a proxy for it. Documented here per the
brief's "identify conflicts before changing architecture" instruction, and
recorded again in `docs/phase-2/SECURITY-TESTS.md`.

## 6. Error model additions

`veyra_contracts.ErrorCategory` gains, additively (nothing renamed —
Phase 1 error codes are unchanged): `APPLICATION_LAUNCH_FAILED`,
`WINDOW_NOT_FOUND`, `WINDOW_NOT_ACTIVE`, `UI_ELEMENT_DISABLED`,
`PATH_NOT_ALLOWED`, `PATH_PROTECTED`, `TARGET_CONTEXT_REQUIRED`,
`INPUT_BLOCKED`, `VERIFICATION_FAILED`, `TOOL_DISABLED`,
`OPERATION_CANCELLED`, `UNKNOWN_WINDOWS_ERROR`, and one addition beyond the
brief's list, `PLATFORM_NOT_SUPPORTED` (needed for the honest non-Windows
failure path described in §2). The brief's `UI_ELEMENT_NOT_FOUND` maps
onto Phase 1's existing `UI_NOT_FOUND` rather than adding a near-duplicate
code — documented in `docs/phase-2/ERROR-RECOVERY.md`.

## 7. Database changes

One additive Alembic migration extends the existing `applications` table
(not a new table — Phase 1 already modeled this entity) with: `aliases`
(JSON list), `publisher` (nullable), `install_source` (nullable),
`risk_level` (`RiskLevel` enum, default `MODERATE` — launching an app is
not read-only), `enabled` (bool, default `True`), `verification_strategy`
(string). A second migration seeds a small curated registry of common,
safe, well-known Windows executables (Notepad, Calculator, File Explorer —
the exact three the brief's functional tests reference) as **registry
entries only** (name/identifier/aliases/risk_level) — never a hard-coded
absolute path; the path itself is resolved at launch time (PATH search,
well-known Windows directories, `App Paths` registry key), per the brief's
"do not assume paths" requirement.

## 8. Tool list for this phase

`application.list_running`, `application.find`, `application.launch`,
`application.focus`, `application.is_running`, `application.close`;
`window.list`, `window.find`, `window.focus`, `window.minimize`,
`window.maximize`, `window.restore`, `window.close`, `window.get_active`,
`window.get_bounds`, `window.get_title`; `filesystem.search`,
`filesystem.list_directory`, `filesystem.get_metadata`, `filesystem.open`,
`filesystem.create_folder`, `filesystem.create_file`, `filesystem.copy`,
`filesystem.move`, `filesystem.rename`; `keyboard.type`, `keyboard.press`,
`keyboard.hotkey`; `mouse.click`, `mouse.double_click`, `mouse.right_click`,
`mouse.move`, `mouse.scroll`; `screen.capture`, `screen.capture_window`,
`screen.capture_active_window`; `ui.find`, `ui.click`, `ui.type`,
`ui.wait_for`. `filesystem.delete` and `process.terminate` are **not
registered** in Phase 2 (brief §7, §6.5) — `filesystem.delete` returns
`TOOL_DISABLED` if ever requested by ID; there is no code path that could
execute it. No generic `system.execute`/`run_command` tool exists anywhere.

## 9. Explicitly out of scope (brief §46, restated)

Full autonomous AI, screen reasoning/visual grounding by a model, voice,
wake word, the final avatar, WhatsApp, email automation, IoT, remote
computers, mobile devices, autonomous destructive operations, CAPTCHA
solving, OTP interception, credential extraction. `filesystem.delete` and
`process.terminate` remain unimplemented placeholders for a future phase
with dedicated CRITICAL-tier review, not built-but-disabled code.

## 10. Documentation set for this phase

`docs/phase-2/{COMPUTER-CONTROL-DESIGN,WINDOWS-UI-AUTOMATION,
APPLICATION-CONTROL,WINDOW-CONTROL,FILESYSTEM-CONTROL,INPUT-CONTROL,
SCREEN-CAPTURE,VERIFICATION,ERROR-RECOVERY,SECURITY-TESTS,PERFORMANCE,
PHASE-2-TEST-RESULTS}.md`, written alongside implementation, each stating
plainly what was verified in this environment versus what is correct
Windows-only code pending verification on real Windows hardware.
