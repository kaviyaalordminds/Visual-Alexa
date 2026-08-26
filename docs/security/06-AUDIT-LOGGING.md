# 06 — Audit Logging

## 1. Principle

Every tool execution — success or failure, SAFE tier or CRITICAL — writes
exactly one `AuditLog` row. This is not optional or best-effort; the Tool
Executor's wrapper (`docs/architecture/04-TOOL-ARCHITECTURE.md` execution
path) writes the audit row in a `finally`-equivalent path so it happens even
if the tool raises.

## 2. Schema

```
AuditLog
  id: str
  correlation_id: str        # ties to a task/request chain (12-EVENTS.md)
  user_id: str
  tool_id: str | None
  action: str
  target: str | None
  risk_level: RiskLevel
  permission_grant_id: str | None    # which grant authorized this, if any
  request_payload_summary: dict      # redacted/summarized, not raw secrets
  result_status: ToolResultStatus
  error_code: str | None
  evidence_tier_used: EvidenceTier | None
  duration_ms: int
  created_at: datetime
```

## 3. What the system must be able to answer (product brief §38)

Every field above exists specifically so these questions are answerable
directly from the `AuditLog` table without reconstructing state from logs:

- "What did VEYRA do?" → `action`, `tool_id`, `target`
- "Why did it do it?" → `correlation_id` joins back to the originating
  `Task`/`Conversation`
- "What tool did it use?" → `tool_id`
- "What permission was checked?" → `permission_grant_id`, `risk_level`
- "What failed?" → `result_status`, `error_code`
- "What was the recovery attempt?" → subsequent `AuditLog` rows sharing the
  same `correlation_id` during a `RECOVERING` task state

## 4. User-facing, not just internal

Unlike most surveyed competitor products (`docs/research/06-SECURITY-RISKS.md`
item 7 — audit logging is largely undocumented/host-app-dependent),
VEYRA's audit log is exposed via `/events` history and a future `/audit`
API surface as a genuine user-facing feature, not solely a debugging aid.

## 5. Redaction rule

`request_payload_summary` must never include values from fields the tool
definition marks `sensitive` in its input schema (e.g., a password field, a
raw secret) — the summarizer redacts these before the row is written, not
after.

## 6. Phase 1 scope

Delivered: schema, write path wired into the (stub) tool executor, and unit
tests asserting a row is written for both success and failure stub
executions. Not delivered: a dedicated `/audit` browsing API beyond what
`/events` already exposes (explicitly deferred, not required for Phase 1
acceptance).
