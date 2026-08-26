# 02 — Permission Model

## 1. Capability-based, not identity-based

VEYRA's AI does not get "the user's access." It gets specific, named
capabilities, each scoped to a tool, an optional target, and a risk tier,
each with its own lifetime. This is the direct architectural response to
`docs/research/03-COMPETITOR-WEAKNESSES.md` item 9 (over-permissioned
agents) and item 23.

## 2. Core types

```
PermissionRequest
  request_id: str
  action: str                 # tool_id
  target: str | None          # e.g. a file path, contact id, device id
  reason: str                 # human-readable justification shown to user
  risk_level: RiskLevel
  affected_resource: str | None
  proposed_arguments: dict
  expiration: datetime | None
  user_decision: PermissionDecision | None   # ALLOW_ONCE | ALLOW_SESSION |
                                              # ALWAYS_ALLOW | DENY | CANCEL
  timestamp: datetime

PermissionGrant
  id: str
  user_id: str
  tool_id: str
  target: str | None          # None = applies to any target for this tool
  risk_level: RiskLevel
  scope: PermissionDecision    # ALLOW_ONCE | ALLOW_SESSION | ALWAYS_ALLOW
  granted_at: datetime
  expires_at: datetime | None  # ALLOW_ONCE/ALLOW_SESSION always expire
  revoked_at: datetime | None
```

## 3. Decision rule the Policy Engine enforces

```
on ToolCallRequest(tool_id, target, ...):
    definition = ToolRegistry.get(tool_id)          # unknown → reject
    if definition.risk_level == CRITICAL:
        require fresh PermissionRequest + explicit ALLOW decision
        (no stored grant, however broad, satisfies CRITICAL — see
         08-SENSITIVE-ACTION-POLICY.md)
    else:
        grant = find valid, unexpired, unrevoked PermissionGrant
                matching (user, tool_id, target-or-None, risk_level<=granted)
        if grant exists: allow
        else: create PermissionRequest, surface to user, block until decided
```

## 4. Revocation

Any `PermissionGrant` can be revoked by the user at any time via the
`/permissions` API; revocation is immediate (checked at call time, not
cached beyond a single request) and itself produces an `AuditLog` entry.

## 5. Phase 1 scope

Delivered: full data model (`Permission`, `PermissionGrant` tables), the
decision-rule pseudocode above implemented as real Policy Engine code with
unit tests, and the `/permissions` API contract (list, grant, revoke). Not
delivered: any real SENSITIVE/CRITICAL tool to exercise this against in
production use (Phase 1's only registered tool is `system.get_status`,
SAFE tier) — the engine is proven correct via unit tests using synthetic
tool definitions, not live traffic.
