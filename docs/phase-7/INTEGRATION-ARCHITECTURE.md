# Integration Architecture

## 1. Shape

```
IntegrationDefinition (id, name, category, auth_method, required_scopes)
        │  registered at startup via IntegrationRegistry.register_definition
        ▼
IntegrationRegistry.connect(session, tool_registry, id, secret=...)
        │  CredentialManager.store_credential(secret) -> ref
        │  Integration row (DB): connected=True, state=CONNECTED, credentials_ref=ref
        ▼
tool_registry.register(tool_def, executor_bound_to(ref))   # per tool
        │
        ▼
execute_tool_call  (same chokepoint every tool already uses)
```

`docs/architecture/11-INTEGRATIONS.md` §2's invariant holds exactly:
"every `Integration` capability that performs an action is registered in
the Tool Registry like any other tool... integrations do not bypass the
Policy Engine." `ToolDefinition.integration_id` (new, nullable) is the
only structural addition needed — it's set on every tool an
`IntegrationBundle` contributes, `None` for every tool that predates
this phase.

## 2. Why DB-backed, not in-memory like `ToolRegistry`

`ToolRegistry` is pure in-memory, rebuilt from code at every process
start — that's fine for it because *what tools exist* is a code-time
fact. *Which integrations a user has connected* is not a code-time
fact — it must survive a restart, or the user would have to reconnect
Gmail every time VEYRA restarts. `IntegrationRegistry` is therefore a
thin service over the real `integrations` table (extended this phase
with `name`/`state`/`scopes`/`connected_at`/`last_health_check_at`),
keyed by `Integration.provider == IntegrationDefinition.id`.
`reconnect_all_on_startup` re-registers every still-connected
integration's tools into the live `ToolRegistry` at boot — the same
"DB rows -> in-memory object, rebuilt wholesale at boot" pattern
`app/services/application_registry.py` already established in Phase 2.
A credential that no longer validates by boot time is surfaced as
`EXPIRED` rather than silently re-registering tools that would
immediately fail `NOT_CONNECTED`.

## 3. `IntegrationState`

`AVAILABLE, INSTALL_REQUIRED, CONNECT_REQUIRED, AUTHORIZING, CONNECTED,
DISCONNECTED, EXPIRED, REVOKED, ERROR, UNAVAILABLE` (brief §23). A never
-connected integration reports `CONNECT_REQUIRED`; `disconnect()` sets
`DISCONNECTED`; a `health_check()` finding an invalid/missing credential
sets `EXPIRED`. `AVAILABLE`/`INSTALL_REQUIRED`/`AUTHORIZING`/`REVOKED`/
`ERROR`/`UNAVAILABLE` are real enum members with no live producer yet —
nothing in this phase needs an install step, a multi-step OAuth
authorization flow, an admin revocation, or a hard error state distinct
from "credential invalid." Reserved for the real integrations a future
phase adds.

## 4. Reconnecting rotates, never leaks

Calling `connect()` on an already-connected integration is a real
rotation: the old `credentials_ref` is deleted from the `CredentialStore`
before the new one is stored, and every tool is re-registered with an
executor bound to the *new* ref. `tests/integration/
test_integrations_api.py::test_reconnecting_rotates_the_credential_and_
revokes_the_old_one` proves the old ref genuinely stops decrypting to
anything, not just that the DB row moved on.

## 5. The reference integration

`app/services/reference_integration.py` — `reference.echo`
(`RiskLevel.SAFE`, one capability). Deliberately not a disguised real
product: it does no network I/O, just validates a stored credential
exists (`NOT_CONNECTED` otherwise) and echoes its input back through the
same `ToolResult` shape every other tool uses. This is intentional — the
platform mechanics (register, connect with a real stored credential,
execute through the real Policy Engine, audit, health-check, disconnect)
are what's under test, not any particular product's API, and a
zero-network reference is deterministic and safe to run in CI forever.

## 6. What's real vs. not

| Piece | Status |
|---|---|
| `IntegrationRegistry` (register/connect/disconnect/health-check/reconnect-on-startup) | **Real** — DB-backed, tested end to end via the real HTTP API |
| Credential storage on connect | **Real** — see `CREDENTIAL-MANAGEMENT.md` |
| `reference.echo` full lifecycle | **Real** — connect, execute, audit, health-check, disconnect all verified |
| A real Gmail/Spotify/WhatsApp/YouTube integration | **Not shipped** — explicitly out of this phase's Stop Condition |
| OAuth2 browser-redirect flow | **Not shipped** — `AuthMethod.OAUTH2` exists as a contract value; no real provider to redirect to |
| `browser`/`communication`/`media` tool categories populated | **Not shipped** — zero tools in these categories still; `reference.echo` uses `CUSTOM` |
