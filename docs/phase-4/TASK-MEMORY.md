# Task Memory

Brief §40/§83: short-term task memory only, never mixed with long-term
personal memory.

## 1. Short-term (Phase 4, this document)

`TaskContext` (`app/services/agent/context.py`) — in-memory, one instance
per `AgentOrchestrator.run` call, discarded when the call returns.
Persisted durably only as `TaskStep` rows (per-step tool results, errors,
retry counts) and the `Task` row's own `result`/`failure_reason`/
`extra_metadata` columns — the database is the durable record, not a
second copy of `TaskContext` itself.

## 2. Long-term (explicitly out of scope, unchanged from Phase 1)

`docs/architecture/09-MEMORY.md`'s `MemoryCategory`/`MemoryRecord`
(Phase 1) is where long-term personal memory belongs in a future phase.
**Nothing in Phase 4 writes to it.** Verified by absence: `grep -r
MemoryRecord app/services/agent` returns nothing.

## 3. No hidden memory (CLAUDE.md)

Every piece of state `AgentOrchestrator` accumulates during a run is
either transient (`TaskContext`, gone when the call returns) or written
to a `Task`/`TaskStep` row a user can already inspect via `GET /tasks/{id}`
and `GET /tasks/{id}/steps` — nothing is written anywhere the existing
API surface can't already show.
