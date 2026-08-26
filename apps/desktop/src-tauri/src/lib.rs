//! VEYRA desktop shell — Phase 1.
//!
//! docs/architecture/02-DESKTOP-ARCHITECTURE.md: this native layer's only
//! Phase 1 job is hosting the React technical shell in the OS-native
//! WebView (WebView2 on Windows). The shell talks to the Local API over
//! plain HTTP from the WebView's JavaScript context — no custom Tauri
//! command is exposed in Phase 1, since there is no OS automation
//! primitive for the shell to need yet. A future command that *does* touch
//! Win32/UI Automation must be reviewed under the same security model as
//! any other tool (docs/security/01-SECURITY-ARCHITECTURE.md) before it is
//! added here.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running the VEYRA desktop shell");
}
