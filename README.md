# VEYRA

**A local-first Visual AI Computer Operating Layer** — not a voice
assistant clone, not a chatbot, not a thin wrapper around a computer-use
model. See `docs/research/VEYRA_DIFFERENTIATION.md` for what that means and
why, and `CLAUDE.md` for the rules this repository is built under.

**Current phase: Phase 1 — landscape research + foundation architecture.**
No live AI, voice, vision, computer control, or IoT exists yet by design —
see `docs/roadmap/PHASE-1-SCOPE.md` for the exact in/out-of-scope boundary
and `docs/roadmap/DEFINITION-OF-DONE.md` for what's actually verified.

## Start here

- `docs/research/` — competitive landscape research and VEYRA's
  differentiation (read this first for *why*)
- `docs/architecture/` — system design (read this for *how*)
- `docs/security/` — permission model, threat model, security architecture
- `CLAUDE.md` — the rules every change in this repo must follow

## Repository layout

```
apps/desktop/            Tauri (Rust) + React/TypeScript desktop shell
services/local-api/       FastAPI backend — the only process with DB access
services/{ai-runtime,voice,vision,device-gateway}/   Future pluggable services (stubs)
packages/contracts/       Shared typed contracts (Python + TypeScript)
packages/{tool,agent,event}-sdk/, packages/shared/    Future SDKs (stubs)
database/                 Alembic migrations + seed data
integrations/              Future official-API adapters (stubs)
avatar/                     Future visual identity (architecture only)
docs/                        Research, architecture, security, API, roadmap
tests/                        unit / integration / security / agent-evals / end-to-end
scripts/                       Dev tooling
```

## Running Phase 1 locally

### Prerequisites
Python 3.11+, Node 20+, Rust/Cargo (for the desktop shell). On Linux, the
desktop shell additionally needs GTK3 + WebKitGTK dev libraries (Windows
uses WebView2, already present on modern Windows).

### Local API

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e packages/contracts/python
pip install -e "services/local-api[dev]"

cd database
alembic -c alembic.ini upgrade head    # creates database/veyra.db

cd ../services/local-api
uvicorn app.main:app --host 127.0.0.1 --port 8756
```

Visit `http://127.0.0.1:8756/docs` for the interactive API docs, or
`http://127.0.0.1:8756/health`.

### Desktop shell (dev mode)

```bash
npm install
cd apps/desktop
npm run dev              # Vite dev server on http://localhost:1420
# in another terminal:
cd src-tauri && cargo build && ./target/debug/veyra-desktop
```

### Tests, lint, type-check

```bash
bash scripts/check-python.sh     # ruff + mypy + pytest for the Python foundation
cd apps/desktop && npm run lint && npm run build   # eslint + tsc + vite build
```

## What Phase 1 is not

Full AI assistant, full planner, full computer automation, full voice, full
vision, full avatar, WhatsApp automation, IoT drivers, autonomous
destructive operations, remote access — all explicitly out of scope. See
`docs/roadmap/PHASE-1-SCOPE.md`.
