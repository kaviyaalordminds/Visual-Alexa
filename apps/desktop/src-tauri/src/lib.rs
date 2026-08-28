//! VEYRA desktop shell.
//!
//! docs/architecture/02-DESKTOP-ARCHITECTURE.md: this native layer's job
//! is hosting the React technical shell in the OS-native WebView
//! (WebView2 on Windows). The shell talks to the Local API over plain
//! HTTP from the WebView's JavaScript context — still no custom Tauri
//! *command* is exposed (no OS automation primitive needs one yet). A
//! future command that does touch Win32/UI Automation must be reviewed
//! under the same security model as any other tool
//! (docs/security/01-SECURITY-ARCHITECTURE.md) before it is added here.
//!
//! Phase 10 P0-1 (docs/phase-10/RELEASE-READINESS.md, docs/phase-10/
//! ARCHITECTURE-AUDIT.md §1): a packaged VEYRA.exe previously had no
//! mechanism to start the Python Local API — nothing else would. In a
//! release build, this module now spawns the `veyra-local-api` sidecar
//! (built by scripts/build-backend-sidecar.py, a PyInstaller freeze of
//! services/local-api — see that script's own docstring) as a child
//! process on startup and terminates it when the app exits. In a debug
//! build (`cargo tauri dev`), this is skipped entirely — the developer
//! workflow (`scripts/dev-backend.bat`) is unchanged, matching this
//! file's own existing `#[cfg_attr(not(debug_assertions), ...)]`
//! precedent in main.rs for exactly this dev/release split.
//!
//! What this file cannot prove from a Linux sandbox: that a real, frozen
//! Windows sidecar binary actually exists and actually starts VEYRA's
//! backend end-to-end — that requires a Windows build and a Windows test,
//! neither possible here. What *is* verified here: this Rust code
//! compiles (`cargo check`), and the spawn/kill logic itself is
//! deliberately simple and directly modeled on tauri-plugin-shell's own
//! documented sidecar API.

#[cfg(not(debug_assertions))]
use std::sync::Mutex;

#[cfg(not(debug_assertions))]
use tauri_plugin_shell::{process::CommandChild, ShellExt};

/// Holds the running sidecar's handle so it can be killed on shutdown.
/// `Mutex<Option<..>>` rather than a plain `Option` because Tauri state
/// must be `Send + Sync`, and this is only ever touched from the main
/// thread's setup/exit callbacks — no real contention, just the type
/// system's requirement.
#[cfg(not(debug_assertions))]
struct SidecarHandle(Mutex<Option<CommandChild>>);

#[cfg(not(debug_assertions))]
fn spawn_backend_sidecar(app: &tauri::AppHandle) {
    use tauri::Manager;

    let sidecar_command = match app.shell().sidecar("veyra-local-api") {
        Ok(cmd) => cmd,
        Err(err) => {
            // Never crash the whole app over this — the WebView still
            // loads; the frontend's own health polling (App.tsx) already
            // reports "Local API unreachable" truthfully if the backend
            // never comes up. A silently-vanished shell is worse than an
            // honest error banner.
            eprintln!("[VEYRA] Failed to prepare Local API sidecar command: {err}");
            return;
        }
    };

    match sidecar_command.spawn() {
        Ok((_receiver, child)) => {
            println!("[VEYRA] Local API sidecar started (pid {})", child.pid());
            if let Some(state) = app.try_state::<SidecarHandle>() {
                *state.0.lock().unwrap() = Some(child);
            }
        }
        Err(err) => {
            eprintln!("[VEYRA] Failed to start Local API sidecar: {err}");
        }
    }
}

#[cfg(not(debug_assertions))]
fn kill_backend_sidecar(app: &tauri::AppHandle) {
    use tauri::Manager;

    if let Some(state) = app.try_state::<SidecarHandle>() {
        if let Some(child) = state.0.lock().unwrap().take() {
            // Best-effort: the sidecar process exiting is not something
            // the desktop shell can meaningfully retry or recover from —
            // this is app teardown, not a request that can fail closed.
            if let Err(err) = child.kill() {
                eprintln!("[VEYRA] Failed to stop Local API sidecar cleanly: {err}");
            } else {
                println!("[VEYRA] Local API sidecar stopped");
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default();

    #[cfg(not(debug_assertions))]
    let builder = builder
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarHandle(Mutex::new(None)))
        .setup(|app| {
            spawn_backend_sidecar(app.handle());
            Ok(())
        });

    #[cfg(not(debug_assertions))]
    let builder = builder.on_window_event(|window, event| {
        use tauri::Manager;
        if let tauri::WindowEvent::CloseRequested { .. } = event {
            kill_backend_sidecar(window.app_handle());
        }
    });

    builder
        .run(tauri::generate_context!())
        .expect("error while running the VEYRA desktop shell");
}
