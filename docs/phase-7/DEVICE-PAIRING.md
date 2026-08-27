# Device Pairing

## 1. The six stages, enforced procedurally

CLAUDE.md: "No device is controllable without completing PAIR ->
IDENTIFY -> AUTHENTICATE -> AUTHORIZE -> REGISTER CAPABILITIES ->
CONTROL, in order, with no stage skippable."

`Device.trust_status` (`UNPAIRED, PAIRING, PAIRED, REVOKED`, Phase 1)
is coarser than these six stages. Rather than exploding that enum, a new
`Device.pairing_stage` column (`DevicePairingStage`: `PAIR, IDENTIFY,
AUTHENTICATE, AUTHORIZE, REGISTER_CAPABILITIES, CONTROL`) tracks exactly
which stage completed, and `DevicePairingService` enforces the order
procedurally — each method requires the device to be at the exact
previous stage (`_require_exact_previous`), raising `PairingStageError`
otherwise. `trust_status` still only reflects the coarse,
externally-meaningful state (`UNPAIRED` until `REGISTER_CAPABILITIES`
completes, `PAIRED` once reached) — the granular stage is an
implementation detail of the service, never a second status a caller
could get out of sync with `trust_status`.

`CONTROL` is the one exception to strict-previous-stage enforcement:
once reached, it stays reachable (`_require_at_least`) — granting a
second capability's permission is not a "stage regression."
`grant_permission` additionally refuses to grant any capability that
`register_capabilities` never actually registered
(`UnregisteredCapabilityError`) — a `DevicePermission` must never
authorize something the device was never said to support.

## 2. Runtime permission cache

`ToolExecutor.execute()` never receives a DB session (see
`app/services/tool_registry.py`), so a device-control tool executor
cannot query `DevicePermission` rows directly at call time.
`DevicePairingService` keeps an in-memory `(device_id, capability_key)
-> expires_at` cache, updated by `grant_permission`/`revoke_permission`
and rebuilt from the real DB rows at startup
(`rebuild_permission_cache_on_startup`) — the same
process-wide-registry-kept-in-sync-with-DB pattern
`orchestrator.py`'s own `_cancellation_events`/`_pause_events` already
established. `is_permission_valid(device_id, capability_key)` is the
one thing a device-control executor consults.

## 3. `MockACDevice`

Brief §166: "Do NOT connect a real AC/fan/TV yet. Create a mock device
provider." Two tools, `iot.mock_ac.set_power`/`.set_temperature`
(`app/services/mock_iot.py`), `RiskLevel.SAFE` (see
`docs/architecture/10-IOT.md` §6 for why), gated entirely by a real
granted `DevicePermission`. Arguments are strictly type-checked — a real
bug this phase's own verification found: `bool(call.arguments.get
("power"))` silently coerces *any* truthy value, including the string
`"false"`, into `True` (Python's classic gotcha). Fixed to reject a
non-bool `power`/non-numeric or out-of-range `celsius` with
`VALIDATION_ERROR` instead of guessing —
`tests/security/test_phase7_platform_security.py::
test_string_false_for_power_is_rejected_not_coerced_to_true` is the
regression test.

## 4. HTTP surface (`app/api/devices.py`)

`POST /devices/pair`, then one route per later stage
(`/{id}/identify`, `/{id}/authenticate`, `/{id}/authorize`,
`/{id}/register-capabilities`, `/{id}/permissions/grant`,
`/{id}/permissions/revoke`) — each a thin wrapper around one
`DevicePairingService` method, which is what actually enforces the
order; these routes are not a second place the rule could be bypassed
from. No generic `/devices/{id}/command` route exists at all —
`tests/security/test_deny_by_default.py::
test_no_generic_command_backdoor_endpoint_exists` asserts this
directly.

## 5. Acceptance tests (brief §166-169)

| # | Scenario | Result |
|---|---|---|
| 166 | Mock device provider, no real AC touched | **Passes** — `MockACDevice`'s only state is an in-memory dict |
| 167 | No remote-PC capability | **Passes** — no `DeviceType` resembling a PC exists, no tool id contains `remote_pc`/`remote_desktop` (`tests/security/test_phase7_platform_security.py`) |
| 168 | "Turn on my AC" with nothing paired never scans/discovers | **Passes** — `test_turning_on_ac_with_nothing_paired_fails_honestly_no_scan`: no device row is ever created, the tool call fails `VALIDATION_ERROR` (missing target) |
| 169 | Connect Mock AC, grant AC_CONTROL, allowed; revoke, blocked | **Passes** — `test_acceptance_grant_then_control_then_revoke_then_blocked` |

## 6. What's not delivered

Real device discovery/network scanning (never attempted, by design — see
§168). A real `Matter`/`HomeAssistant`/vendor-API adapter — interface
stubs only, per brief §134-135. A full "un-pair" cascade — see
`docs/security/04-DEVICE-TRUST.md` §6.
