# VEYRA — Phase 12 Production Readiness Checklist

Checked items were verified for real this session (live backend process,
real HTTP calls, real test suite runs) — never assumed from reading code
alone. Unchecked items are honestly unmet, each with why.

- [x] Database migration works — unchanged, automatic, already tested
      (`tests/unit/test_database_migrate.py`), re-verified this phase's
      live backend start.
- [x] Backend starts — live-verified (`/ready` returned `{"ready":true}`
      within seconds of a fresh, isolated `VEYRA_APP_DATA_DIR`).
- [ ] Frontend starts — `npm run dev`/`vitest`/`tsc`/`eslint` all pass in
      this sandbox; a real Tauri desktop window has not been launched
      (no GUI/Windows host here — unchanged blocker from Phase 10).
- [x] WebSocket connects — real, unchanged since Phase 9; this phase adds
      genuine CONNECTING/CONNECTED/RECONNECTING/ERROR/DISCONNECTED
      granularity to what the frontend can observe and display (was
      previously a single boolean).
- [x] Health API works — `GET /system` real per-subsystem checks,
      now including `browser` and `memory` (previously absent fields);
      `GET /health`/`GET /ready` unchanged and real.
- [x] AI provider health works — real generic HTTP provider + health
      check, honestly reports NOT CONFIGURED/DEGRADED/CONNECTED/ERROR
      (unchanged this phase — audited, found sound, not rebuilt).
- [x] Voice health works — honestly NOT CONFIGURED (no real audio
      pipeline exists yet) — unchanged, still true.
- [x] Vision health works — real OCR/capture detection — unchanged.
- [x] Computer-control health works — real platform-gated check —
      unchanged.
- [x] Browser health works — **new this phase**: real check (an open
      session → CONNECTED; none but Playwright installed → NOT
      CONNECTED; Playwright missing → NOT CONFIGURED), live-verified.
- [x] File system works — unchanged, real, already tested.
- [x] Application registry works — unchanged, real, already tested.
- [x] Memory works — real CRUD (unchanged) plus **new this phase**: a
      real per-subsystem health check in `/system`, a bulk clear
      endpoint (`DELETE /memory[?category=]`), and `memory.updated`
      events on every write — all live-verified.
- [x] Permission system works — unchanged, unconditional Policy Engine
      gate, re-verified via the full security test suite.
- [x] Security system works — unchanged; this phase adds real
      `permission.*`/`security.*` event observability at existing
      decision points, verified end-to-end (CAPTCHA stop, unsafe URL,
      confirmation approve/deny).
- [x] IoT remains isolated — unchanged (deny-by-default, full six-stage
      pairing lifecycle); this phase adds real `iot.device_connected/
      disconnected` and `iot.command_started/completed` events at the
      real pairing/tool-execution chokepoints, verified end-to-end.
- [x] Audit logging works — unchanged; this phase adds a real
      `audit.record_created` event published from the single
      `write_audit_log` chokepoint every tool call already goes through
      — verified every tool call publishes exactly one.
- [x] Error recovery works — unchanged (Phase 11's real REPLAN, retry,
      recovery-strategy bounding); re-verified via the full test suite.
- [~] Offline mode works — real, but scoped: `ConnectivityManager`
      exists for voice only (Phase 5); general AI-task offline
      detection relies on the existing DEGRADED/ERROR health-check
      path rather than a dedicated "offline" concept. Not extended
      this phase (see audit §8 P1/P2) — flagged, not silently claimed
      complete.
- [ ] Windows packaging works — still blocked on a real Windows machine
      (unchanged since Phase 10 — `docs/phase-10/RELEASE-CHECKLIST.md`);
      this sandbox cannot build or test a `.exe`/`.msi`.
- [ ] Fresh installation works — same blocker as packaging.
- [ ] Upgrade installation works — same blocker as packaging.
- [ ] Uninstallation works — same blocker as packaging.
- [x] No secrets exposed — re-confirmed: no API key/token ever reaches
      the frontend or a log line; the audit log's redaction logic
      unchanged and re-tested.
- [x] No fake status indicators — the entire audit (PHASE_12_AUDIT.md)
      was built specifically to catch this; every REAL/PARTIAL/MISSING
      finding is evidence-based, and every new status field this phase
      added (`browser`, `memory`) is backed by a genuine check, never a
      static literal.
- [x] No critical console errors — desktop frontend's reconnect path has
      zero `console.*` calls (confirmed by audit and unchanged); ESLint
      clean across the whole frontend.
- [x] No startup crashes — live-verified fresh backend start; full test
      suite (778+ backend tests) green.

## What would unblock every remaining item

The same single blocker as Phase 10: a real Windows machine (or Windows
CI runner) to build and test the actual installer, and a real
GUI-capable host to launch the Tauri desktop shell. Every item that can
be verified without one has been, this phase included.
