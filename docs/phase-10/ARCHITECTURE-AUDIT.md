# Phase 10 — Architecture Audit (Windows Packaging Focus)

Scope: does the current architecture actually support being installed and
run as a standalone Windows application, independent of a developer's
source tree? This is the single most important question Phase 10 asks,
and the answer today is **no, not yet** — detailed below, with exactly
what's missing and why.

## 1. Backend process ownership — the core gap

Confirmed by direct inspection of `apps/desktop/src-tauri/`:

- No `externalBin` (Tauri's sidecar-binary mechanism) in `tauri.conf.json`.
- No `tauri-plugin-shell` dependency in `Cargo.toml`.
- No `std::process::Command` usage anywhere in `src-tauri/src/`.
- `lib.rs` registers zero custom Tauri commands; its own doc comment says
  the shell "talks to the Local API over plain HTTP... no custom Tauri
  command is exposed in Phase 1."

**Conclusion**: a packaged `VEYRA.exe` today has no mechanism to start,
stop, or supervise the Python backend. `apps/desktop/src/api.ts` and
`useAvatarSocket.ts` both hardcode `127.0.0.1:8756`, assuming something
*else* already put a backend there. Today that "something else" is a
developer manually running `scripts/dev-backend.bat`. Double-clicking an
installed `VEYRA.exe` would open a WebView against a dead port.

## 2. Installer configuration

`tauri.conf.json`'s `bundle` section (`active: true`,
`targets: ["nsis", "msi"]`) uses Tauri's defaults for everything else — no
custom NSIS/WiX template, no license/EULA, no custom install path, no
code-signing config. All four referenced icon files exist on disk. This
part is fine as a starting point but produces, today, a frontend-only
installer per §1 above.

## 3. Updater, system tray, autostart — all absent

Confirmed absent by grep (no `tauri-plugin-updater`, no
`tauri-plugin-tray`/`SystemTray`/`TrayIcon`, no
`tauri-plugin-autostart`/registry `Run`-key code). Expected for Phase 1
scope; real gaps against the Phase 10 spec's "System Tray" and "Start with
Windows" requirements, not yet built.

## 4. Window/process lifecycle

Single default Tauri window, no `onCloseRequested` handler, no
minimize-to-tray, no single-instance enforcement
(`tauri-plugin-single-instance` absent, `capabilities.json` is empty
`{}`). Default behavior: closing the window fully quits the process, and
nothing prevents launching multiple simultaneous VEYRA instances (each
would independently hit the same hardcoded loopback port).

## 5. Resource paths for a packaged build — would break

`services/local-api/app/core/config.py:23`:
```python
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DB_PATH = _REPO_ROOT / "database" / "veyra.db"
```
This anchors the database (and, less rigorously, `credentials_store_path`
and `browser_downloads_dir`, which are still bare cwd-relative strings —
`"./credentials.enc.json"`, `"./browser-downloads"`) to a fixed depth
below `config.py`'s own location. This assumes a live git-checkout layout.
In a PyInstaller-frozen or otherwise repackaged backend, `__file__`
resolves somewhere inside a temp extraction directory or wherever the
bundled module physically lands — neither reliably 4 parents above a
`database/` directory. Even in the best case (exact directory nesting
preserved under `C:\Program Files\VEYRA\`), writing there requires admin
rights the app shouldn't need, and isn't multi-user-safe.

## 6. App data directory — confirmed wrong for an installed app

No `app_data_dir`/`AppData`/Tauri path-resolver usage anywhere in
`apps/desktop/` (the frontend never touches the filesystem at all — all
data-path decisions are the Python backend's, per §5). None of the
backend's three real data paths resolve to `%APPDATA%\VEYRA` or any
per-user Windows convention.

## Architecture questions from the Phase 10 brief, answered honestly

- *Can VEYRA support additional AI/vision/STT/TTS providers without
  rearchitecting?* Yes — `LLMProvider`/`VisionProvider` are already real
  `Protocol`s with exactly one `NotConfigured*` implementation each; a new
  concrete provider is a new adapter module, no interface change needed
  (confirmed, Phase 9 audit).
- *Can VEYRA be installed on another Windows PC and run without the dev
  environment?* **No, not today** — §1 and §6 above are the reasons.
  This is the actual architectural limitation Phase 10 exists to close,
  and it requires real implementation work (a sidecar/spawn mechanism,
  Windows-app-data-relative paths with an env-var override for dev), not
  a doc fix.
- *Can VEYRA recover from a service failure?* Within-process, partially
  (Phase 9's fault-isolation fixes). Cross-process (the whole Local API
  dying), no — no supervisor exists (see PRODUCTION-AUDIT.md).
- *Can VEYRA be upgraded safely?* No updater exists yet (§3) — expected
  for this phase, flagged as future work, not attempted here.

## What this sandbox cannot verify

Building and running an actual `.exe`/`.msi`, testing WebView2
provisioning, testing a real Windows installer UX, and a genuine
"clean machine" test all require a real Windows host. Nothing in this
audit claims those were run — they weren't, and can't be from here.
