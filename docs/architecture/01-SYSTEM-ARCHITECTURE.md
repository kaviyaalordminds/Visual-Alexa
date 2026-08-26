# 01 — System Architecture

## 1. Overview

VEYRA is a local-first Windows desktop product composed of a thin native
shell, a local backend (the "local API"), a local database, and a set of
pluggable services (AI reasoning, voice, vision, device gateway) that are
either local processes or optional cloud calls behind a provider interface.

```
┌─────────────────────────────────────────────────────────────────┐
│  Windows PC (primary, trusted environment)                       │
│                                                                    │
│  ┌───────────────┐        ┌────────────────────────────────┐    │
│  │ Desktop Shell  │◄──────►│ Local API (FastAPI, 127.0.0.1) │    │
│  │ (Tauri + React)│  HTTP/ │                                  │    │
│  │                │  WS    │  ┌───────────┐  ┌────────────┐ │    │
│  └───────────────┘        │  │  Policy    │  │   Tool     │ │    │
│                             │  │  Engine    │  │  Registry  │ │    │
│                             │  └───────────┘  └────────────┘ │    │
│                             │  ┌───────────┐  ┌────────────┐ │    │
│                             │  │ Task       │  │  Event     │ │    │
│                             │  │ Runtime    │  │  Bus       │ │    │
│                             │  └───────────┘  └────────────┘ │    │
│                             └───────────┬──────────────────┘    │
│                                          │                        │
│                             ┌────────────▼─────────────┐         │
│                             │  SQLite (local-first DB)  │         │
│                             └────────────────────────────┘         │
│                                                                    │
│  Optional local services (future phases, out of Phase 1 scope):   │
│  ai-runtime · voice · vision · device-gateway                     │
└─────────────────────────────────────────────────────────────────┘
                 │ optional, explicit, provider-agnostic
                 ▼
        Cloud AI provider (only when AI mode = HYBRID/CLOUD
        and the user has configured it — see 03-AI-ARCHITECTURE.md)
```

## 2. Component responsibilities

| Component | Responsibility | Phase 1 status |
|---|---|---|
| Desktop Shell (`apps/desktop`) | Native window, tray, lifecycle, hosts the React UI via WebView | Minimal shell: connects to local API, renders status |
| React technical shell (`apps/desktop/src`) | Renders status screen; future: conversation UI, avatar, task monitor | Minimal status screen only |
| Local API (`services/local-api`) | Owns policy engine, tool registry, task runtime, event bus, DB access; the only component allowed to touch the database | `/health`, `/system`, contracts, DB, migrations |
| Database (SQLite) | Durable local state: users, tools, permissions, tasks, conversations, memory, devices, audit log | Schema + migrations, no production data yet |
| ai-runtime, voice, vision, device-gateway | Future pluggable services | Directory + interface stubs only (§39 of brief) |
| Browser extension | Future DOM-aware browser control bridge | Directory placeholder only |
| Integrations (email, WhatsApp, media, browser, IoT) | Future official-API adapters | Directory + interface stubs only |

## 3. Why this shape

- **Single source of truth for security**: the Local API is the only process
  with database access and the only process that can invoke a tool. The
  desktop shell is a thin, replaceable client — it cannot bypass policy
  checks because it has no direct path to execute a tool or touch the DB.
- **Local-first by construction**: the Local API binds to `127.0.0.1` only
  in Phase 1 (no remote access surface), and every subsystem functions with
  zero outbound network calls except an explicitly configured cloud AI
  provider call.
- **Provider independence**: `ai-runtime` is a boundary, not a specific
  vendor SDK import scattered through the codebase — see
  `03-AI-ARCHITECTURE.md`.

## 4. Process boundaries (why they matter for security)

Each box above is a separate OS process. This matters because the security
model (`docs/security/01-SECURITY-ARCHITECTURE.md`) depends on the LLM never
having a direct code path to OS primitives: even if a future `ai-runtime`
process is compromised or manipulated via prompt injection, it can only ever
*call the Local API's tool endpoints*, which re-validate every request
against the Policy Engine independently of anything the AI process claims.

## 5. Data flow at a glance

See `13-DATA-FLOW.md` for the full real-time vs. background path breakdown.
In short: user input → Desktop Shell → Local API → Policy Engine → Tool
Registry → Tool Executor (stubbed in Phase 1) → Verification → Audit Log →
Event Bus → back to Desktop Shell/avatar.

## 6. What must NOT change without architectural review

- The Local API must remain the single point of database access.
- The Desktop Shell must never be given direct database or tool-execution
  access that bypasses the Local API.
- No component may default to binding on a non-loopback interface.
