# 13 — Data Flow / Performance Architecture

## 1. Real-time path vs. background path

```
REAL-TIME PATH (must stay low-latency, never blocked by background work)
  Wake word → STT → Language detection → Intent → Short planning →
  Tool execution (policy-checked) → TTS response

BACKGROUND PATH (never allowed to block the real-time path)
  File/content indexing → Memory embedding → Analytics →
  Maintenance/cleanup jobs → Model downloads → Device discovery
```

## 2. Enforcement in Phase 1

The Local API runs background-shaped work (future indexing, maintenance) on
separate asyncio tasks / a dedicated worker queue, never inline within a
request handler that serves the real-time conversational path. Phase 1 has
no real background jobs yet, but the FastAPI app structure
(`services/local-api/app`) separates `api/` (request/response, real-time
shaped) from `services/` (where background-shaped logic will live), so this
separation is structural from the start rather than retrofitted.

## 3. End-to-end request flow (Phase 1, concretely)

```
Desktop Shell (React)
   │ GET /health, GET /system   (poll on interval)
   ▼
Local API (FastAPI)
   │ reads SystemSetting rows via DB session
   ▼
SQLite
   │ returns current component status
   ▼
Local API → JSON response
   ▼
Desktop Shell renders CONNECTED/NOT CONFIGURED status per component
```

## 4. Future full task flow (contract, not yet executable)

```
User input → Desktop Shell → Local API /tasks (create)
   → TaskRuntime (RECEIVED → UNDERSTANDING → PLANNING)
   → Policy Engine (WAITING_PERMISSION if needed)
   → Tool Executor (EXECUTING → OBSERVING → VERIFYING)
   → RECOVERING (on failure, bounded) or COMPLETED/FAILED
   → EventBus publishes task.* events throughout
   → AuditLog records every tool call
   → Desktop Shell/avatar reflects state via /events WebSocket
```

## 5. Phase 1 scope

Delivered: the structural separation (api/ vs services/), the concrete
health/system flow above, and the full future flow as a documented,
type-checked contract. Not delivered: a live end-to-end task execution
(no real tools, no real planner).
