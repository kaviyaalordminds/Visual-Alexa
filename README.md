# VEYRA

**A local-first Visual AI Computer Operating Layer** — not a voice
assistant clone, not a chatbot, not a thin wrapper around a computer-use
model. See `docs/research/VEYRA_DIFFERENTIATION.md` for what that means and
why, and `CLAUDE.md` for the rules this repository is built under.

**Current phase: Phase 10 — production hardening, Windows packaging,
reliability & release engineering**, built on Phases 1-9 (real computer
control, vision/OCR, browser automation, agent orchestration, voice
conversation logic, an avatar, a plugin/integration platform, and — as of
Phase 9's subsystem activation — real, honest AI/Voice/Vision/Computer-
Control/IoT health checks with no fake CONNECTED states). See
`docs/phase-10/PRODUCTION-READINESS-REPORT.md` for an honest, per-
component READY/PARTIALLY READY/NOT READY score, and
`docs/phase-10/PRODUCTION-RUNBOOK.md` for how to run, diagnose, and
troubleshoot it. `docs/roadmap/PHASE-1-SCOPE.md` and
`docs/roadmap/DEFINITION-OF-DONE.md` remain accurate for Phase 1's own,
narrower scope.

## Start here

- `docs/research/` — competitive landscape research and VEYRA's
  differentiation (read this first for *why*)
- `docs/architecture/` — system design (read this for *how*)
- `docs/security/` — permission model, threat model, security architecture
- `CLAUDE.md` — the rules every change in this repo must follow

## Repository layout

```
apps/desktop/            Tauri (Rust) + React/TypeScript desktop shell —
                          in a release build, spawns its own Local API
                          sidecar (see services/local-api/sidecar_entry.py)
services/local-api/       FastAPI backend — the only process with DB access
services/computer-control/  Real Win32/UI-Automation engine (Windows-gated)
services/vision/            Real OCR (tesseract); no real vision-model provider yet
services/voice/              Real conversation logic; no real audio pipeline yet
services/ai-runtime/         Placeholder — the real LLM connectivity layer lives in
                              services/local-api/app/services/agent/ instead
services/device-gateway/     Placeholder — pairing/authorization is real and lives in
                              services/local-api/app/services/device_pairing.py instead
packages/contracts/       Shared typed contracts (Python + TypeScript)
packages/{tool,agent,event}-sdk/, packages/shared/    Future SDKs (stubs)
database/                 Alembic migrations + seed data
integrations/              Future official-API adapters (stubs)
avatar/                     Future visual identity (architecture only)
docs/                        Research, architecture, security, API, roadmap, phase-10
tests/                        unit / integration / security / agent-evals / end-to-end
scripts/                       Dev tooling + scripts/build-backend-sidecar.py (Windows-only)
```

## Running VEYRA locally (development mode)

### Prerequisites
Python 3.11+, Node 20+, Rust/Cargo (for the desktop shell). On Linux, the
desktop shell additionally needs GTK3 + WebKitGTK dev libraries (Windows
uses WebView2, already present on modern Windows). `tesseract-ocr` must be
on `PATH` for `services/vision`'s real OCR engine to report itself
available (`apt-get install -y tesseract-ocr` on Debian/Ubuntu) — without
it, Vision's OCR capability check and `tests/unit/test_ocr_engine.py` and
friends correctly report/fail as unavailable rather than silently passing.
For real wake-word/STT/TTS voice hardware, see
`docs/voice-hardware/SETUP.md` (optional — voice defaults to honestly
`NOT CONFIGURED` without it).

### Local API

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/contracts/python
pip install -e "services/local-api[dev]"

cd services/local-api
uvicorn app.main:app --host 127.0.0.1 --port 8756
```

Migrations now run automatically on startup — no separate `alembic
upgrade head` step is required (a manual one is still safe to run and is
a no-op if already current). The database, credentials store, and logs
now live in a real per-user app-data location, not inside this repo —
see `app/core/paths.py` and `docs/phase-10/PRODUCTION-RUNBOOK.md` for the
exact path per OS, or set `VEYRA_APP_DATA_DIR` to override it (used by
the test suite for isolation). `scripts\dev-backend.bat` /
`scripts\start-veyra.bat` automate this on Windows.

Visit `http://127.0.0.1:8756/docs` for the interactive API docs,
`http://127.0.0.1:8756/health` for liveness, `/ready` for readiness, or
`/system` for full per-subsystem diagnostics.

### Desktop shell (dev mode)

```bash
npm install
cd apps/desktop
npm run dev              # Vite dev server on http://localhost:1420
# in another terminal:
cd src-tauri && cargo build && ./target/debug/veyra-desktop
```

A dev build never spawns a backend sidecar itself — start the Local API
separately, as above (this is a deliberate dev/release split; see
`apps/desktop/src-tauri/src/lib.rs`). A release build does spawn its own
sidecar; see `docs/phase-10/ARCHITECTURE-AUDIT.md` and
`scripts/build-backend-sidecar.py` for how it's built (Windows-only).

### Tests, lint, type-check

```bash
bash scripts/check-python.sh     # ruff + mypy + pytest for the Python foundation
cd apps/desktop && npx tsc -b && npx eslint . && npx vitest run
```

## Production status

See `docs/phase-10/PRODUCTION-READINESS-REPORT.md` for an honest,
per-component score, and `docs/phase-10/RELEASE-CHECKLIST.md` for exactly
what's verified vs. still blocked on a Windows build/test machine.

## What is not implemented yet

A real LLM-backed general planner (the planner remains deterministic/
template-based by design), a real vision *model* provider (OCR and
screen capture are real), memory-informed target resolution, and any
real external integration (WhatsApp, email, etc.) or real IoT protocol —
all clearly reported as such by their own health checks (see
`docs/subsystem-activation/`), never faked.

A real, local, offline STT/TTS/wake-word audio pipeline now exists
(openWakeWord/whisper.cpp/Piper — see `docs/voice-hardware/SETUP.md`);
only real microphone/speaker hardware verification is still pending
(this repo's own dev/CI sandbox has no audio hardware to test against).
