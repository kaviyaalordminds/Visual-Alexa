# API Documentation

The Local API (`services/local-api`) is a FastAPI application; its OpenAPI
schema is generated automatically and is the source of truth for exact
request/response shapes (CLAUDE.md "API rules"). With the server running:

- Interactive docs: `http://127.0.0.1:8756/docs`
- Raw OpenAPI schema: `http://127.0.0.1:8756/openapi.json`

## Phase 1 endpoint summary

| Endpoint | Purpose | Doc |
|---|---|---|
| `GET /health` | Liveness check | — |
| `GET /system` | Component status for the status screen | `docs/architecture/13-DATA-FLOW.md` |
| `GET/PATCH /settings` | System settings (mic/screen/devices/remote defaults) | `docs/security/05-DATA-PROTECTION.md` |
| `GET /tools`, `GET /tools/{id}`, `POST /tools/{id}/invoke` | Tool Registry + execution | `docs/architecture/04-TOOL-ARCHITECTURE.md` |
| `GET/POST /permissions`, `POST /permissions/{id}/revoke` | PermissionGrant lifecycle | `docs/security/02-PERMISSION-MODEL.md` |
| `GET/POST/PATCH/DELETE /memory` | Memory CRUD | `docs/architecture/09-MEMORY.md` |
| `GET /devices` | Device list (empty until a future phase adds an adapter) | `docs/security/04-DEVICE-TRUST.md` |
| `GET/POST /conversations`, `GET/POST /conversations/{id}/messages` | Conversation history | — |
| `GET/POST /tasks`, `GET /tasks/{id}` | Task creation with mandatory `TaskBudget` | `docs/architecture/14-TASK-LIFECYCLE.md` |
| `GET /integrations` | Integration registry (empty in Phase 1) | `docs/architecture/11-INTEGRATIONS.md` |
| `WS /events` | Event bus fan-out | `docs/architecture/12-EVENTS.md` |

See `docs/roadmap/PHASE-1-SCOPE.md` for what each of these does and does
not do yet.
