# Phase 7 Test Results

Run in this environment (Linux container, real SQLite, real HTTP via
`httpx.AsyncClient`, real Chromium via Playwright for the frontend,
real `alembic upgrade head`/`downgrade base` round-trip against a
throwaway SQLite file), 2026-08-27.

## 1. Summary

- **Full backend suite**: 558 passed, 0 failed, 2 skipped (pre-existing
  Phase 2 Windows-only skips) — `scripts/check-python.sh`.
- **New backend tests this phase**: 86 across 9 new files
  (`test_tool_discovery.py` 10, `test_credential_manager.py` 12,
  `test_integration_registry.py` 5, `test_device_pairing.py` 14,
  `test_plugin_registry.py` 9, `test_future_adapters.py` 5,
  `test_integrations_api.py` 10, `test_mock_iot.py` 7,
  `test_plugins_api.py` 6, `test_phase7_platform_security.py` 8 — that's
  10 files/86, `test_phase7_platform_security.py` counted once), plus
  `test_tool_registry.py`/`test_tools_api.py` extended in place and
  `test_deny_by_default.py` rewritten for the flow that now exists (see
  §3).
- **Frontend**: 58 `vitest` tests (was 53 after Phase 6), +5 in
  `PlatformPanel.test.tsx`; `tsc -b`, `eslint .`, and `vite build` all
  clean.
- **Lint/types**: `ruff check` clean across all five Python packages and
  `tests/`; `mypy` clean — `veyra_contracts` (15 files), `computer_control`
  (25), `vision` (19), `veyra-voice` (20), `app` (86).
- **Migration chain**: `alembic upgrade head` and `alembic downgrade
  base` both verified clean against a fresh, throwaway SQLite file — see
  §3's first bug for why this specifically needed checking.

## 2. What was verified for real vs. reviewed-only vs. not shipped

| Area | Status |
|---|---|
| `ToolRegistry.unregister/disable/enable` | **Real** — unit-tested, wired into `execute_tool_call`'s own gate |
| `search_tools` dynamic discovery | **Real** — pure, tested to 500 synthetic tools; wired into the real `GET /tools?query=` against the live 50+-tool registry |
| `IntegrationRegistry` (connect/disconnect/health-check/reconnect-on-startup) | **Real** — DB-backed, verified end to end through the real HTTP API |
| `CredentialManager`/`FileCredentialStore` | **Real** — real Fernet encryption, verified the plaintext never touches disk or any API response/audit row |
| `reference.echo` integration | **Real** full lifecycle — deliberately not a real product, see `INTEGRATION-ARCHITECTURE.md` §5 |
| `DevicePairingService` six-stage flow | **Real** — procedurally enforced, no stage skippable, verified via both direct unit tests and the real HTTP API |
| `MockACDevice` control tools | **Real** mechanics (permission gating, argument validation), mock device (no real AC) |
| `PluginRegistry` default-deny lifecycle | **Real** — install/grant/trust/enable/disable/remove all DB-backed and tested; brief §170's acceptance scenario passes |
| Desktop shell Platform panel | **Real** — calls the actual HTTP API, verified in a real Chromium browser against the real backend (not just mocked `vitest`) |
| A real Gmail/WhatsApp/Spotify/browser integration | **Not shipped** — explicit Stop Condition |
| Real Matter/Home Assistant/remote-PC adapters | **Not shipped** — interface-only stubs (`app/services/future_adapters.py`), never imported by `main.py`, never reachable from any route (`tests/unit/test_future_adapters.py` asserts both) |
| Real plugin code execution/sandboxing | **Not shipped** — nothing in this phase ever imports or runs a plugin's actual code |
| Real DPAPI credential storage | **Not shipped** — no Windows host in this environment, same limitation as Phase 2 |
| A live LLM-driven planner consuming `search_tools` | **Not shipped** — `TaskPlanner` is still Phase 4's deterministic rule-based mapper; see `TOOL-DISCOVERY.md` §1 |

## 3. Real bugs found and fixed during this phase's own verification

1. **`alembic upgrade head` has never actually worked from an empty
   database, since Phase 5.** `bdcb05c63501` (Phase 1's own seed
   migration) imported the *live* `app.db.seed_defaults.DEFAULT_SETTINGS`
   dict instead of embedding its own frozen snapshot of what Phase 1
   actually seeded. Phase 5 later added 16 more keys to that same
   shared dict — from that point on, `bdcb05c63501` silently started
   re-seeding Phase 5's `voice.*`/`wake_word.*`/`stt.*`/`tts.*`/`audio.*`
   keys too, colliding with `c1a2f3b4d5e6` (the migration Phase 5
   actually wrote to seed exactly those keys, whose own docstring
   already assumed "the pre-existing keys were already seeded by
   bdcb05c63501" — true only for a frozen snapshot, never true of a
   live import). This raised a `UNIQUE constraint failed:
   system_settings.key` `IntegrityError` on every fresh
   `alembic upgrade head`, undetected because the test suite (and every
   dev run) creates its schema via `Base.metadata.create_all`, never by
   replaying migrations from scratch — this phase's own new migration
   was the first thing to actually exercise the full chain. Fixed by
   freezing `bdcb05c63501`'s own 10-key snapshot inline. Verified: the
   full chain now applies and downgrades cleanly against a throwaway
   SQLite file (`alembic upgrade head` / `alembic downgrade base`
   round-trip, §1).
2. **`bool(call.arguments.get("power"))` in the mock AC executor
   silently coerced any truthy value — including the string `"false"`
   — into `True`.** A malformed or adversarial `{"power": "false"}`
   argument would have turned the AC *on*. Fixed to strictly require a
   real `bool` (rejecting with `VALIDATION_ERROR` otherwise); the
   temperature executor got the analogous fix plus a sane numeric
   range check. Regression test:
   `tests/security/test_phase7_platform_security.py::
   test_string_false_for_power_is_rejected_not_coerced_to_true`.
3. **`PluginRegistry.install` referenced `PluginPermissionRow.plugin_id
   = row.id` before `row.id` existed.** `IDMixin.id`'s default (`
   new_uuid`) is a Python-side default evaluated by SQLAlchemy at
   flush/insert time, not at object-construction time — reading
   `row.id` immediately after `session.add(row)` but before a flush
   returned `None`, causing a `NOT NULL constraint failed:
   plugin_permissions.plugin_id` on every single `install()` call.
   Caught immediately by `tests/unit/test_plugin_registry.py`'s own
   first test run (9/9 failed before the fix). Fixed with an explicit
   `await session.flush()` before referencing `row.id`.

Also two smaller drift fixes carried out along the way, in the same
spirit as Phase 6's TypeScript-contracts find: the TypeScript
`ToolCategory` was missing `"vision"` (a real Phase 3 addition never
mirrored) and `ToolDefinition` was missing the Phase 6-era `keywords`/
`integration_id` fields — both corrected while touching these contracts
for Phase 7's own additions.

## 4. Acceptance tests (brief §166-172)

See `DEVICE-PAIRING.md` §5 for §166-169 in detail (all pass). §170
(plugin permission escalation) — see `PLUGIN-ARCHITECTURE.md` §5,
passes. §171 (prompt injection) —
`tests/security/test_phase7_platform_security.py::
test_reference_echo_treats_adversarial_text_as_data_never_instructions`
passes: adversarial text handed to `reference.echo` is echoed back
verbatim as data, with no side effect anywhere else in the system. §172
(credential lifecycle) — connect, verify the secret is encrypted at
rest and absent from every API response/audit row, disconnect, verify
the ref no longer decrypts: all pass (`test_credential_manager.py`,
`test_phase7_platform_security.py`, `test_integrations_api.py`).

## 5. Known limitations

- No real external integration exists — `reference.echo` is explicitly
  a platform-proving stand-in, not a product feature.
- No LLM-driven planner exists yet to consume `search_tools` for real;
  the primitive is built and tested ahead of that caller.
- `DevicePairingService`'s permission cache and `PluginRegistry`'s tool
  builders are process-local, in-memory state (mirroring
  `orchestrator.py`'s own established pattern) — correct for this
  single-process architecture (CLAUDE.md: "the Local API is the only
  process that can invoke a tool"), but would need a different design
  if the Local API ever became multi-process.
- No "un-pair" cascade for devices (see
  `docs/security/04-DEVICE-TRUST.md` §6) — only per-capability
  `revoke_permission`.
- The desktop shell's Platform panel is diagnostic, in the same
  deliberately-modest spirit as `DevConsole.tsx` — not a finished
  integrations/devices/plugins management UI (no OAuth redirect flow to
  drive, no plugin marketplace, no permission-editing UI beyond
  grant/revoke buttons).

## 6. Definition of Done (brief §175)

Honest pass over the brief's own checklist:

**Tool platform** — Tool contract ✓ (additive `keywords`/
`integration_id`) · Tool registry ✓ (`register/unregister/get/list/
enable/disable`) · Tool executor ✓ (`execute_tool_call`, unchanged
chokepoint) · Tool validation ✓ (Policy Engine + per-tool argument
checks) · Result normalization ✓ (`ToolResult`, unchanged) · Cancellation
— unchanged, Phase 4's existing mechanism · Timeout — unchanged, Phase
4's existing `TaskBudget` · Retry policy ✓ (new `AUTH_ERROR`/
`NOT_CONNECTED` added to `RecoveryManager`'s permanent-failure set;
`RATE_LIMITED` added to retryable) · Rollback abstraction — not extended
this phase, no new reversible-action tool was added.

**Integration platform** — Integration contract ✓ · Integration
registry ✓ · Integration gateway — folded into `IntegrationRegistry`
itself rather than a separate class (no second layer of indirection
needed for one reference integration) · Health monitoring ✓ · Connect/
disconnect ✓ · Versioning — not addressed; `IntegrationDefinition` has
no version field yet, matching `ToolDefinition`'s own pre-existing gap.

**Security** — Default deny ✓ (plugins, device permissions, integration
credentials all start denied/disconnected) · Granular permissions ✓
(plugin permissions, device capability keys) · Risk levels — unchanged
enum, reused · Confirmation integration — unchanged Policy Engine path,
reused as-is · Credential manager ✓ · Audit logs ✓ (unchanged
`write_audit_log`, exercised by every new tool call) · Prompt injection
defense ✓ (verified for the one new surface that could plausibly be
misread as one, `reference.echo`) · Plugin permission isolation ✓.

**AI** — Dynamic tool discovery ✓ (`search_tools`, no live consumer yet)
· Tool selection — unchanged, `ToolSelector`'s hallucination guard ·
Structured tool calls — unchanged `ToolCallRequest` · Tool-call
validation ✓ (new argument-type checks in the mock IoT executors) ·
Agent loop protection — unchanged Phase 4 `LoopBudgetTracker`, applies
to every new tool for free · Multi-step tool execution — unchanged.

**PC** — Phase 2 tools exposed through the registry — already true
before this phase, unchanged.

**Browser** — Browser abstraction/tool layer/extension bridge — **not
built**, explicit Stop Condition.

**Communication** — Integration abstraction ✓ (the generic
`IntegrationBundle`/`Integration` interface; no communication-specific
implementation) · OAuth architecture — contract-level only
(`AuthMethod.OAUTH2`), no live flow.

**Media** — Not built (no media-specific integration).

**IoT** — Device abstraction ✓ · Pairing architecture ✓ · Permission
architecture ✓ · Mock device implementation ✓.

**Plugins** — Manifest ✓ · Registry ✓ · Permission model ✓ · SDK
foundation — the `IntegrationBundle`/tool-builder pattern serves this
role; no separate `@veyra/integration-sdk` package was built · Lifecycle
✓ (install/trust/enable/disable/remove).

**UI** — Integration management ✓ (modest) · Permission management ✓
(grant/revoke buttons) · Connected devices ✓ · Security center — not
built as a distinct view (the existing panels together cover its
content) · Audit history — not exposed in the UI (the data exists via
`AuditLog`, no dedicated screen).

**Testing** — Unit ✓ · Integration ✓ · Security ✓ · Prompt injection ✓
· Failure tests — covered incidentally (permission-denied, disconnected,
expired-credential paths), no dedicated network-failure simulation
(nothing here makes a real network call to fail) · Recovery tests —
unchanged Phase 4 coverage, applies to new tools for free · Performance
tests ✓ (the 500-tool `search_tools` scale test).

**Documentation** — Complete for what this phase built (this file plus
`PHASE-7-IMPLEMENTATION-PLAN.md`, `TOOL-DISCOVERY.md`,
`INTEGRATION-ARCHITECTURE.md`, `CREDENTIAL-MANAGEMENT.md`,
`DEVICE-PAIRING.md`, `PLUGIN-ARCHITECTURE.md`, plus updates to the five
Phase 1 architecture/security docs this phase's work touched).

## 7. Technical debt

- `IntegrationRegistry`/`DevicePairingService`/`PluginRegistry` each
  reimplement a similar "in-memory runtime state kept in sync with a
  DB-backed source of truth, rebuilt at startup" pattern independently
  rather than sharing a common base — each was small enough on its own
  that factoring out a shared abstraction felt premature (CLAUDE.md:
  "don't add abstractions beyond what the task requires"); worth
  revisiting if a fourth such registry appears.
- `PluginManifest.dependencies` is tracked but never resolved/enforced.
- No rate limiting exists anywhere in the integration/plugin/device
  surface (brief §84/§123) — moot without a real external API to be
  rate-limited by yet.
