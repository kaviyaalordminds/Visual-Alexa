# 09 — Memory Architecture

## 1. Categories

| Memory type | Purpose | Example |
|---|---|---|
| `ShortTermMemory` | Current conversation/task working context, not persisted beyond the session | "the file the user just mentioned" |
| `ConversationMemory` | Persisted conversation history | past chat turns |
| `TaskMemory` | Record of past tasks and their outcomes | "last time I searched for invoices, these were the results" |
| `UserPreferenceMemory` | Explicit or inferred user preferences | "use Spotify for music" |
| `SemanticMemory` | General facts learned about the user's environment | "the user's default browser is Firefox" |
| `WorkflowMemory` | User-defined aliases/workflows | "office folder" → `D:\Projects\Office` |
| `DeviceMemory` | Known/paired devices and their last-seen state | paired IoT devices, trust status |

## 2. Non-negotiable properties (product brief §17)

Every memory record, regardless of category, must be:

- **User-controlled**: nothing is written to memory as a side effect the
  user cannot see coming — writes are attributable to a specific
  conversation/task/tool event.
- **Inspectable**: a `/memory` API surface lists all records with their
  category, content, source, and timestamps.
- **Editable**: any record's content can be updated via the API.
- **Deletable**: any record (or all records in a category) can be deleted.
- **Auditable**: every write/edit/delete is itself an `AuditLog` entry.

No hidden memory. This is a hard requirement, not a UX nicety — see
`CLAUDE.md` "Memory rules."

## 3. Data model

`Memory` table (see `database/migrations`): `id`, `user_id`, `category`,
`key` (nullable, used for alias-style lookups like `WorkflowMemory`),
`content` (structured JSON), `source` (`conversation_id` / `task_id` /
`user_explicit`), `created_at`, `updated_at`, `expires_at` (nullable).

## 4. Workflow alias resolution (future; contract defined now)

```
User: "When I say office folder, use D:\Projects\Office."
   → planner recognizes this as a WorkflowMemory-defining utterance
   → writes a Memory row: category=WORKFLOW, key="office folder",
     content={"path": "D:\\Projects\\Office"}

User (later): "Open my office folder."
   → planner resolves "office folder" against WorkflowMemory before
     falling back to file search
```

This contract is specified in `packages/contracts` and exercised by an
agent-eval fixture in Phase 1; no live planner exists yet to run it against.

## 5. Phase 1 scope

Delivered: full schema, CRUD API contracts, audit-on-write requirement.
Not delivered: any automatic memory writing (requires a live conversational
agent, out of Phase 1 scope) or semantic embedding/retrieval (vector search
is a documented future extension point — see `21-TECHNOLOGY-EVALUATION`
database discussion in `docs/architecture/01-SYSTEM-ARCHITECTURE.md` and the
database migration comments).
