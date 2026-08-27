# Phase 7 Implementation Plan — Universal Tool, Integration & Plugin Platform

Written before substantial implementation, per the established Phase 2-6
discipline: what the repository actually has today (re-verified, not
assumed), what's genuinely reusable vs. new, and the decisions made with
rationale.

## 1. What Phase 1-6 actually implemented (repository inspection findings)

A large fraction of "Phase 7" already exists, under different names, in
the Python `services/local-api` backend rather than the brief's suggested
`integrations/` TypeScript tree — that tree is real (`services/`,
`apps/`, `packages/`), but CLAUDE.md's own architecture is unambiguous
("the Local API is the only process with database access and the only
process that can invoke a tool"), so the brief's `integrations/*.ts`
structure is adapted into `services/local-api/app/services/*.py`, exactly
the same adaptation every prior phase made against its own brief.

- **`ToolRegistry`** (`app/services/tool_registry.py`, 49 lines) already
  exists and is real: `register/get/get_executor/list(category)`, a
  process-lifetime in-memory dict keyed by `definition.id`, rejecting
  registration without `risk_level`/`required_permission`
  (`ToolRegistrationError`). **50 tools are registered today** (1 system,
  40 Phase 2 computer-control, 9 Phase 3 vision) via the identical
  `build_X_tools(...) -> list[tuple[ToolDefinition, executor]]` pattern
  in each category module. `ToolCategory.BROWSER/COMMUNICATION/MEDIA/IOT`
  already exist in the enum with zero tools registered — these are
  exactly the categories Phase 7's integrations populate.
- **`PolicyEngine`** (`app/services/policy_engine.py`) already
  real: `evaluate(session, user_id, tool_id, risk_level, target) ->
  PolicyDecision`. SAFE always allowed; CRITICAL always denied +
  requires_confirmation (unconditionally, in code, matching CLAUDE.md's
  "no stored grant... satisfies a CRITICAL check"); MODERATE/SENSITIVE
  checked against real `PermissionGrant` rows (target-scoped,
  expiry-aware). **This is the one gate every Phase 7 tool call —
  integration-backed or not — must keep going through.**
- **`execute_tool_call`** (`app/services/tool_execution.py`) is the
  single real chokepoint: registry lookup -> policy evaluate -> execute
  -> audit (always, success or failure) -> event publish. Two callers
  today (`POST /tools/{id}/invoke`, `AgentOrchestrator`) — Phase 7 adds
  no second path; every integration-backed tool call goes through this
  exact function, unchanged.
- **`CredentialManager` does not exist at all.** `credentials_ref`
  columns exist on `Integration`/`Device` (opaque reference, never a raw
  secret) but nothing ever writes to them.
  `docs/security/05-DATA-PROTECTION.md` §1 already specifies the design:
  DPAPI on Windows (undeliverable here, no Windows host), and "a local
  encrypted-at-rest fallback... `SECRET_KEY`-derived" on non-Windows —
  `Settings.secret_key` (`app/core/config.py:29`) was already added for
  exactly this, unused until now. This phase builds the real fallback
  store and the real `CredentialManager` around it.
- **`Integration`/`Device`/`DeviceCapability`/`DevicePermission` tables
  already exist**, matching `docs/architecture/11-INTEGRATIONS.md` §2's
  documented `Integration` interface and `docs/architecture/10-IOT.md`'s
  device-trust model almost exactly — but **nothing ever inserts a row
  into any of them**. `GET /integrations` and `GET /devices` are
  real-but-always-empty reads. `root-level integrations/{browser,email,
  iot,media,whatsapp}/` are each a one-paragraph README with zero code —
  the documented location for real adapter code.
- **The `Tool` DB table (`tools`) is completely dead** despite its own
  docstring claiming `ToolRegistry` upserts into it — it doesn't; the
  registry is in-memory only. This is the same category of doc-vs-code
  drift Phase 6 found and fixed in the TypeScript contracts. Fixed here
  (§3.7) since Phase 7 needs a persisted tool catalog for versioning/UI
  discovery anyway.
- **There is no LLM-driven planner yet** — `TaskPlanner`
  (`app/services/agent/planner.py`) is a deterministic, rule-based
  intent-to-plan mapper (`_plan_open_application`, `_plan_search_files`,
  `_plan_open_file`), never a prompt with tool definitions stuffed into
  it. `ToolSelector.select()` only rejects a hallucinated tool id after
  the planner already chose one — it doesn't narrow a catalog for an LLM.
  Brief §26-27/§158's "hundreds of tools, don't hand the model every
  definition" problem therefore has no live LLM caller to fix a
  regression for yet — this phase builds the real, tested discovery
  primitive (`search_tools`) so it's ready the moment a future phase adds
  an LLM planner, without inventing a caller that doesn't exist.
- **`RecoveryManager` (Phase 4) is task/step-failure-specific, not
  directly reusable** for "an integration went unreachable" — it's a
  pure decision function keyed to `TaskBudget.max_recovery_attempts`/
  `max_replans`, concepts that don't map onto integration health. The
  *pattern* (pure, bounded, error-taxonomy-driven decision function) is
  worth mirroring for `IntegrationHealthService`, not the class itself.
- **The desktop shell has zero integration/device/settings UI** and no
  router — `App.tsx` is a single page (status grid + avatar + dev
  console). Backend routes for `/integrations`, `/devices`, `/permissions`
  already exist but the frontend `api.ts` never calls them.

## 2. Scope decisions (what this phase builds vs. explicitly defers)

Per the brief's own Stop Condition (§176) and CLAUDE.md's Phase 7
description, this phase builds **the platform**, not real external
integrations:

**Built for real, tested, wired through the existing
registry/policy/executor/audit chain — no new chokepoint:**

1. Contract additions: `ToolDefinition.keywords`/`integration_id`
   (additive), `IntegrationState`, `AuthMethod`, `PluginState` enums,
   `IntegrationDefinition`/`ConnectionResult`/`IntegrationResult`/
   `PluginManifest` contracts, three new `ErrorCategory` members
   (`AUTH_ERROR`, `NOT_CONNECTED`, `RATE_LIMITED` — everything else the
   brief's §32 taxonomy needs already exists under an existing name).
2. `IntegrationRegistry` — real, DB-backed (`integrations` table
   extended additively), connect/disconnect/health-check/list, states
   per §23, real credentials via `CredentialManager`.
3. `CredentialManager` with a real, working `FileCredentialStore`
   (Fernet, keyed from `Settings.secret_key`) — the actual non-Windows
   fallback `05-DATA-PROTECTION.md` already promised. DPAPI remains
   documented-only (no Windows host in this environment, same category
   as Phase 2's Windows-only backends).
4. Dynamic tool discovery: `search_tools(query, category)` over the real
   50-tool registry, `GET /tools?query=...`, load-tested at hundreds of
   tools.
5. **One reference integration** (`ReferenceIntegration` /
   `reference.echo`) — deliberately not a real product (no Gmail/
   Spotify/WhatsApp implementation, per the Stop Condition), demonstrating
   the full lifecycle end to end: manifest, registration, real credential
   storage, execution through `execute_tool_call`, audit, health check,
   disconnect (credential revoked). Chosen specifically because it needs
   zero network access — deterministic, no flakiness, no accidental
   real-world API commitment.
6. **One mock IoT device** (`MockACDevice`) with a real
   `DevicePairingService` enforcing PAIR -> IDENTIFY -> AUTHENTICATE ->
   AUTHORIZE -> REGISTER CAPABILITIES -> CONTROL in strict, unskippable
   order (a new `pairing_stage` column makes "no stage skippable" an
   enforced invariant, not just a comment). Control tools
   (`iot.mock_ac.set_power`/`.set_temperature`) go through the same
   `ToolRegistry`/`PolicyEngine`, gated by a real `DevicePermission` row.
   No real network scan, no real device discovery — "Turn on the AC"
   with nothing paired must fail honestly (§168).
7. Plugin system skeleton: `PluginManifest` contract, `PluginRegistry`
   (DB-backed `plugins`/`plugin_permissions` tables), states per §63,
   default-deny permissions, install/enable/disable/remove — with one
   mock plugin fixture exercising the acceptance test in §170.
8. Security tests for all of the above: unauthorized/invalid-permission
   tool calls, expired credential, revoked integration, malicious tool
   arguments, plugin permission escalation, prompt-injection-as-data
   (an integration's returned content is never executed as a command).
9. A modest desktop-shell addition: an Integrations panel and a Devices
   panel (list + connect/disconnect/pair), in the same unstyled,
   diagnostic spirit as `DevConsole.tsx` — still not "the final UI"
   for this surface, matching Phase 1's own restraint.

**Explicitly not built, per the brief's Stop Condition (§176):**

- No real Gmail/WhatsApp/Spotify/YouTube/browser-automation integration.
- No real Matter/Home Assistant adapter — `MatterAdapter`/
  `HomeAssistantAdapter` exist only as documented interface stubs that
  raise `NotImplementedError`, per §134-135's own "prepare... do not
  implement" instruction.
- No real remote-PC or mobile-device control — `RemoteDeviceAdapter`
  is an interface stub, permanently `DISABLED_BY_DEFAULT`; a security
  test asserts no tool resembling remote-PC control is ever registered.
- No live OAuth flow against a real provider (none exists to test
  against) — the state machine and grant/scope model are real; the
  actual browser-redirect step is documented as the extension point a
  real provider would need, the same honesty Phase 5 applied to
  `NotConfigured` audio providers.
- No browser extension bridge implementation — Phase 2/3 never built
  browser automation either; this stays a documented interface.

## 3. Key design decisions

### 3.1 Integrations are Tool Registry citizens, not a parallel system

`docs/architecture/11-INTEGRATIONS.md` §2 already states the invariant:
"Every `Integration` capability that performs an action is registered in
the Tool Registry like any other tool... integrations do not bypass the
Policy Engine." `ToolDefinition.integration_id` (new, nullable) is the
only structural addition needed to express "this tool belongs to that
integration" — `IntegrationRegistry.connect(...)` calls
`tool_registry.register(...)` for each of the integration's tools only
once connected (nothing to invoke before that), and disabling/
disconnecting an integration removes its tools from the live registry.

### 3.2 `IntegrationRegistry` mirrors `ToolRegistry`'s shape, but is DB-backed

Unlike `ToolRegistry` (pure in-memory, rebuilt at every process start
from code), integrations need to survive a restart already `CONNECTED`
(the user shouldn't have to reconnect Gmail every time VEYRA restarts).
`IntegrationRegistry` therefore is a thin service over the real
`integrations` table (extended with `name`, `state`, `scopes`,
`connected_at`, `last_health_check_at` — additive, via Alembic
migration, matching Phase 4/5's own precedent), not an in-memory
singleton. At startup, connected integrations are reloaded from the DB
and their tools re-registered into the live `ToolRegistry` — the same
"DB rows -> in-memory object, rebuilt wholesale at boot" pattern
`application_registry.py` already established in Phase 2.

### 3.3 `CredentialManager`: real store, honestly-scoped backend

A `CredentialStore` `Protocol` (`store`/`retrieve`/`delete`), mirroring
the `ToolExecutor` `Protocol` pattern. One real implementation ships:
`FileCredentialStore`, using `cryptography`'s `Fernet` (a well-audited,
established AEAD construction — CLAUDE.md: "never invent custom
cryptography... use established platform mechanisms") with a key derived
via PBKDF2-HMAC from `Settings.secret_key` and a fixed, documented salt
(acceptable for a documented dev/non-Windows fallback; production
Windows builds use DPAPI, unaffected by this choice). `cryptography` is
a new, justified dependency — the stdlib has no high-level authenticated
encryption primitive, and `hashlib`/`hmac` alone would mean hand-rolling
crypto, which CLAUDE.md explicitly forbids. `WindowsDPAPICredentialStore`
is a documented extension point (the same `CredentialStore` `Protocol`),
not implemented — no Windows host exists in this environment, the exact
category Phase 2 already established for Windows-only code.

### 3.4 Device pairing: a real state machine, not just a permissive enum

`DeviceTrustStatus` (`UNPAIRED, PAIRING, PAIRED, REVOKED`) is coarser
than CLAUDE.md's six named stages. Rather than exploding the enum,
`DevicePairingService` enforces the six stages procedurally against a
new `pairing_stage` column (`PAIR, IDENTIFY, AUTHENTICATE, AUTHORIZE,
REGISTER_CAPABILITIES, CONTROL` — a new, narrow enum used only here),
raising if a caller attempts a stage before its predecessor completed.
`trust_status` still only reflects the coarse, externally-meaningful
state (`UNPAIRED` until `REGISTER_CAPABILITIES` completes, `PAIRED`
once `CONTROL` is reachable) — the granular enforcement is an
implementation detail of the service, not a second parallel status field
a caller could get out of sync with `trust_status`.

### 3.5 Reference integration: `ReferenceIntegration` (`reference.echo`)

Deliberately not a disguised real product. Its one capability
(`reference.echo`, `RiskLevel.SAFE`) does no network I/O — it validates
that a credential exists (rejecting `NOT_CONNECTED` otherwise) and
echoes its input back through the exact same `ToolResult` shape every
other tool uses. This is intentional: the platform mechanics (register,
connect with a real stored credential, execute through the real Policy
Engine, audit, health-check, disconnect) are what's under test, not any
particular product's API — and a zero-network reference is
deterministic and safe to run in CI forever, unlike a live call to any
real service.

### 3.6 Plugins: default-deny, explicit grants, one mock plugin

`PluginManifest.permissions` is a flat list of scope strings (mirroring
`ToolDefinition.required_permission`'s existing plain-string
convention, not a new typed permission enum — consistent with how the
codebase already treats permission scopes as opaque strings evaluated by
the Policy Engine). `PluginRegistry.install(manifest)` always lands a
plugin in `UNTRUSTED` with zero granted permissions; `grant(plugin_id,
permission)` is the only way a scope becomes usable, and a plugin's tool
registrations only reach the live `ToolRegistry` once `ENABLED` — never
on install alone. The one mock plugin (`tests/fixtures` — requests
`filesystem.read` + `network.access`) exists purely to drive the
acceptance test in brief §170: install, verify requested-but-ungranted
`filesystem.write` never becomes usable.

### 3.7 Fixing the dead `tools` table

`ToolRegistry.register()` now also upserts a `Tool` row (by unique
`tool_id`) when a DB session is available, making the previously-dead
table real — needed for Phase 7's own tool catalog/versioning use case,
and it closes the exact doc-vs-code drift Phase 6 already found once in
this codebase (the TypeScript contracts). `GET /tools` still reads the
live in-process registry (unchanged) — the DB row exists for
integration-tool bookkeeping and future querying, not as a second source
of truth for what's currently invocable.

## 4. Development order followed

Repository analysis (this document) -> contracts -> `IntegrationRegistry`
-> `CredentialManager` -> dynamic tool discovery -> reference integration
-> mock IoT device + pairing -> plugin skeleton -> security tests ->
minimal UI -> documentation -> full verification, commit, push. Mirrors
the brief's own §161 ordering, adapted to skip steps that don't apply
(no separate "integrate Phase 2/3/4/5/6" step — those integrations are
what §3.1-3.2 already wire through, not a distinct phase of work).
