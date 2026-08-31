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
//! Background / system-tray mode: closing the window hides it to the
//! system tray rather than quitting. The tray icon shows a context menu
//! with "Show VEYRA" (brings the window back) and "Quit" (kills the
//! sidecar in release builds and exits). Left-clicking the tray icon
//! directly shows and focuses the window. This means the Local API
//! backend keeps running after the window is hidden, which is the
//! intended behaviour — IoT automations, background tasks, etc. continue
//! operating without a visible UI.

#[cfg(not(debug_assertions))]
use std::sync::Mutex;

#[cfg(not(debug_assertions))]
use tauri_plugin_shell::{process::CommandChild, ShellExt};

use tauri::{
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

/// Holds the running sidecar's handle so it can be killed on shutdown.
/// `Mutex<Option<..>>` rather than a plain `Option` because Tauri state
/// must be `Send + Sync`, and this is only ever touched from the main
/// thread's setup/exit callbacks — no real contention, just the type
/// system's requirement.
#[cfg(not(debug_assertions))]
struct SidecarHandle(Mutex<Option<CommandChild>>);

#[cfg(not(debug_assertions))]
fn spawn_backend_sidecar(app: &tauri::AppHandle) {
    let sidecar_command = match app.shell().sidecar("veyra-local-api") {
        Ok(cmd) => cmd,
        Err(err) => {
            // Never crash the whole app over this — the WebView still
            // loads; the frontend's own health polling (App.tsx) already
            // reports "Local API unreachable" truthfully if the backend
            // never comes up.
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
    if let Some(state) = app.try_state::<SidecarHandle>() {
        if let Some(child) = state.0.lock().unwrap().take() {
            if let Err(err) = child.kill() {
                eprintln!("[VEYRA] Failed to stop Local API sidecar cleanly: {err}");
            } else {
                println!("[VEYRA] Local API sidecar stopped");
            }
        }
    }
}

fn show_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn build_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let show_item = MenuItemBuilder::with_id("show", "Show VEYRA").build(app)?;
    let quit_item = MenuItemBuilder::with_id("quit", "Quit VEYRA").build(app)?;
    let menu = MenuBuilder::new(app)
        .items(&[&show_item, &quit_item])
        .build()?;

    let icon = app
        .default_window_icon()
        .cloned()
        .expect("[VEYRA] No app icon configured — cannot build tray icon");

    TrayIconBuilder::new()
        .icon(icon)
        .menu(&menu)
        .tooltip("VEYRA — running in background")
        .on_tray_icon_event(|tray, event| {
            // Left-click on the tray icon → show and focus the window.
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_window(tray.app_handle());
            }
        })
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                show_window(app);
            }
            "quit" => {
                // In release builds, kill the backend sidecar before exit so
                // the Python process doesn't linger as an orphan.
                #[cfg(not(debug_assertions))]
                kill_backend_sidecar(app);
                app.exit(0);
            }
            _ => {}
        })
        .build(app)?;

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default();

    // Release only: register the shell plugin and spawn the Local API sidecar.
    #[cfg(not(debug_assertions))]
    let builder = builder
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarHandle(Mutex::new(None)))
        .setup(|app| {
            spawn_backend_sidecar(app.handle());
            build_tray(app)?;
            Ok(())
        });

    // Debug: only build the tray (no sidecar needed — dev-backend.bat already
    // runs the Local API separately).
    #[cfg(debug_assertions)]
    let builder = builder.setup(|app| {
        build_tray(app)?;
        Ok(())
    });

    // Intercept the OS close request and hide the window to the tray instead
    // of allowing the app to quit. The user exits via the tray menu "Quit".
    let builder = builder.on_window_event(|window, event| {
        if let tauri::WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            let _ = window.hide();
        }
    });

    builder
        .run(tauri::generate_context!())
        .expect("error while running the VEYRA desktop shell");
}
