# Phase 1 Scope

Referenced from `docs/research/VEYRA_DIFFERENTIATION.md` and throughout
`docs/architecture/`. This is the explicit in/out-of-scope boundary for
Phase 1, matching the product brief §39.

## In scope (implemented)

1. Repository structure
2. Project configuration
3. Documentation structure (research, architecture, security)
4. `CLAUDE.md`
5. Technology configuration (Tauri, React/TS, FastAPI, SQLite, Alembic)
6. Minimal Windows-targeted desktop shell (Tauri host, verified building in
   this environment against the Linux target; see
   `docs/architecture/02-DESKTOP-ARCHITECTURE.md` for what is/isn't verified)
7. Minimal React technical shell
8. Minimal local API (FastAPI)
9. Health endpoint (`/health`)
10. Database connection (SQLite via SQLAlchemy)
11. Initial schema/migrations (Alembic)
12. Event model (`EventBus`, WebSocket transport, `system.health_changed`)
13. Tool contracts (`ToolDefinition`, `ToolRegistry`, `ToolExecutor`, etc.)
14. Permission contracts (`PermissionRequest`, `PermissionGrant`)
15. Task state machine (`TaskState`, `TaskBudget`)
16. Error model (typed `ErrorInfo`, error categories)
17. Logging foundation (structured logging with correlation IDs)
18. Configuration management (`.env`-based settings)
19. Environment configuration (`.env.example`)
20. Initial tests (unit, integration, security)

## Out of scope (explicitly not implemented)

- Full AI assistant / live LLM integration
- Full planner / autonomous multi-step execution
- Full computer automation (no real tool executors)
- Full voice pipeline (no STT/TTS integration)
- Full vision pipeline (no screen capture/OCR/vision model integration)
- Full avatar (architecture only, no character assets/animation)
- WhatsApp automation
- IoT device drivers (data model + policy only)
- Autonomous destructive operations
- Remote access

Interfaces and stubs are used throughout so future phases implement behavior
behind existing contracts rather than re-architecting.

## Definition of Done

See `docs/roadmap/DEFINITION-OF-DONE.md`.
