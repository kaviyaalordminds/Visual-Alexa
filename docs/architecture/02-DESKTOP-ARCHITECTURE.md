# 02 — Desktop Architecture

## 1. Technology decision

**Decision: Tauri (Rust host) + React/TypeScript UI, targeting Windows as
the primary/supported platform.**

| Option | Why considered | Advantages | Disadvantages | Risk |
|---|---|---|---|---|
| C# / .NET / WinUI 3 | Listed as initial candidate; native Windows-first stack | Deepest first-party Windows integration (Win32, UI Automation, DPAPI all native .NET); WebView2 is Microsoft's own control | Requires the .NET SDK + Windows to build/test at all — **not buildable or verifiable in this Linux-based Phase 1 development/CI environment**; heavier runtime | High for Phase 1 verifiability |
| Electron | Common cross-platform desktop shell choice | Huge ecosystem, easy React integration | Ships its own Chromium (large footprint), weaker natural fit for calling Win32/UIA from JS, higher memory use | Medium |
| **Tauri (chosen)** | Rust host + OS-native WebView | Uses **WebView2 on Windows automatically** (satisfying the brief's WebView2 candidate without requiring the .NET SDK); small footprint; Rust's `windows-rs` crate gives first-class access to Win32, UI Automation, and DPAPI for future phases — comparable depth to .NET for the control layer that matters most; **buildable and testable in this Phase 1 environment**, since Rust/Cargo and Linux WebKit dev libraries are available, unlike the .NET SDK | Smaller ecosystem than Electron/.NET; team needs Rust for the native shell layer | Low for Phase 1; acceptable trade-off long-term given the UIA/DPAPI access story |

**Decision**: Tauri. It is the only candidate that is both (a) capable of
deep native Windows integration in later phases via `windows-rs` (Win32, UI
Automation, DPAPI — the exact APIs `05-COMPUTER-CONTROL.md` and
`docs/security/05-DATA-PROTECTION.md` depend on) and (b) actually buildable
and verifiable inside this Phase 1 development environment, so "the desktop
shell builds and runs" is a claim this repository can prove rather than
assert. WinUI 3/.NET remains a documented alternative to revisit if the team
gains a native Windows CI runner; the architecture keeps the native shell
layer (`apps/desktop/src-tauri`) isolated from the React UI precisely so
this decision is revisitable without rewriting the frontend.

**Known Phase 1 limitation**: this container has no display server. `cargo
build --release` produces a real Windows-installable-shaped binary (cross
compilation to `.exe` is a future CI concern) and is verified to compile
successfully in this environment against the Linux target; actually
launching and visually inspecting a window requires either a developer's own
Windows/Linux desktop or a headless display (Xvfb) — see the final report
for exactly what was and wasn't verified.

## 2. Structure

```
apps/desktop/
├── src/                  # React technical shell (status screen)
├── src-tauri/
│   ├── src/main.rs       # Tauri host: window lifecycle, tray (future),
│   │                     # local-api process supervision (future)
│   ├── Cargo.toml
│   └── tauri.conf.json
├── index.html
├── package.json
└── vite.config.ts
```

## 3. Responsibilities

- Own the OS window and (future) system tray icon.
- Load the React technical shell via the OS-native WebView (WebView2 on
  Windows).
- Poll/subscribe to the Local API for status (`/health`, `/system`) and
  render connection state — this is the entire Phase 1 UI responsibility.
- Future phases: supervise the Local API process lifecycle, host the
  avatar renderer, mediate OS-level permission prompts (mic/screen), bridge
  native Win32/UIA calls the browser sandbox cannot make directly.

## 4. What the desktop shell must never do (Phase 1 and beyond)

- Never call OS automation primitives directly from the WebView's JavaScript
  context — any such capability must be exposed as an explicit, narrowly
  scoped Tauri command reviewed under the same security model as any other
  tool (see `docs/security/01-SECURITY-ARCHITECTURE.md`).
- Never hold its own copy of or direct access to the SQLite database — all
  state comes from the Local API.
- Never silently enable microphone or screen capture; both require explicit
  user action surfaced in the UI (product brief §29).
