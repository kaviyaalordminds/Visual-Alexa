# Application Control

## Resolution flow (brief §6.2, §20)

```
"Open Chrome"
  → ApplicationRegistry.resolve_entry("Chrome")   # alias/name/identifier
                                                    # lookup; unknown ->
                                                    # ApplicationNotFoundError,
                                                    # disabled -> ApplicationDisabledError
  → ApplicationRegistry.resolve_executable_path()  # shutil.which() over
                                                    # entry.executable_candidates
                                                    # — never a stored/assumed
                                                    # absolute path
  → WindowsApplicationBackend.launch(path, args)   # subprocess.Popen([...],
                                                    # shell=False) — list argv,
                                                    # reviewed by
                                                    # tests/security/test_subprocess_argv_safety.py
  → verification: is_running(pid) checked before VERIFIED is ever returned
```

An unregistered name (`"unknown.exe"`) never reaches step 3 — `resolve_entry`
raises before any path resolution or process spawn is attempted. This is
enforced by construction, not by convention: `WindowsApplicationBackend.launch`
is never called with anything but an already-validated path from the registry.

## The registry is database-backed (Phase 1 continuity)

Phase 1's `applications` table (`services/local-api/app/models/application.py`)
already existed as a stub. Phase 2 extends it (migration
`63d3d077887d_phase_2_extend_applications_table_for_.py`) with `aliases`,
`executable_candidates`, `publisher`, `install_source`, `risk_level`,
`enabled`, `verification_strategy`, and seeds three entries (migration
`7a90f572da0d_phase_2_seed_default_application_.py`): Notepad, Calculator,
File Explorer — the exact three the brief's own functional tests (§32)
reference. Seeded rows are registry *entries* only; `executable_candidates`
names are searched via `shutil.which` at launch time, never a stored path.
`app/services/application_registry.py` loads these rows into an in-memory
`computer_control.registry.ApplicationRegistry` once at process startup
(mirroring the existing `ToolRegistry` bootstrap pattern).

## Tools and risk tiers

| Tool | Risk | Why |
|---|---|---|
| `application.list_running` | SAFE | Read-only. |
| `application.find` | SAFE | Read-only. |
| `application.launch` | SAFE | Matches the product brief's own §9 example list verbatim ("SAFE: ... open application"). |
| `application.focus` | SAFE | Cosmetic, fully reversible. |
| `application.is_running` | SAFE | Read-only. |
| `application.close` | MODERATE | Reversible (the app can be relaunched), but can prompt an unsaved-changes dialog — not read-only/cosmetic. |

`application.close` sends a **graceful, application-level close request**
(`pywinauto`'s `window.close()` — equivalent to clicking the window's own
close button) — it never calls `Process.terminate()`/`kill()`. Arbitrary
process termination is explicitly out of Phase 2 scope (brief §6.5) and no
code path in this repository can perform it — there is no
`process.terminate` tool, and `WindowsApplicationBackend.close` doesn't
call the psutil termination APIs at all.

## Verification

`application.launch`'s `ActionResult` is only `VERIFIED` (not just
`EXECUTED`) when `backend.is_running(pid)` returns `True` after the launch
call returns — per docs/phase-2 §21, "do not claim success merely because
a launch command returned successfully." `application.close` is `VERIFIED`
only when the process backend confirms the process is no longer running.

## What's verified here vs. Windows-only

The registry resolution logic (`computer_control.registry`) is fully
tested against a real, safe, cross-platform executable substituted for
Notepad (`tests/unit/test_application_registry.py`, using `python3` as the
"known application"). `WindowsApplicationBackend` itself
(`computer_control/windows/applications.py`) is real, reviewed code but
cannot run in this container — see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2. The
Policy-Engine/verification/error-mapping orchestration around it is
exercised against a fake `ApplicationBackend`
(`tests/integration/test_fake_backed_computer_control.py`).
