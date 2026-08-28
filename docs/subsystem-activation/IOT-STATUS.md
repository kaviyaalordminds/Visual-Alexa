# IoT Subsystem Status

**Current status: NOT CONNECTED** — no device is paired. This is the
correct, expected default per the task's own acceptance criteria, not an
error, and remains true after this activation on every machine until a
user explicitly pairs a device.

## What changed this activation

`/system`'s `iot` field used to read a static `external_devices.enabled`
settings flag — a global on/off switch with no relationship to whether
any device was actually paired. It now calls
`DevicePairingService.has_any_active_permission()` (new this activation),
a real check against the same in-memory permission cache
`DevicePairingService` already used to gate every device-control tool
call — `CONNECTED` only once at least one paired device has a genuinely
active (non-revoked, non-expired) permission grant.

## The device lifecycle (already real, unchanged)

```
DISCOVER -> USER SELECTS DEVICE -> PAIR -> IDENTIFY -> AUTHENTICATE -> AUTHORIZE -> REGISTER CAPABILITIES -> CONTROL
```

`app/services/device_pairing.py`'s `DevicePairingService` enforces this
strictly in order — each stage requires the exact previous stage to have
completed (`_require_exact_previous`); skipping is not possible. Already
verified real and correct in `docs/PHASE-9-AUDIT.md`; unchanged here.

## DeviceAdapter — the new seam for future protocols

`app/services/device_adapter.py` (new this activation) defines the
`DeviceAdapter` Protocol: `discover()`, `connect()`, `send_command()`,
`disconnect()`, keyed by `protocol_id`. **No concrete adapter ships** —
matching CLAUDE.md's Phase 8 Stop Condition and the task's own explicit
"do not create fake IoT integrations" instruction. A future Matter,
Home Assistant, or manufacturer-API adapter implements this Protocol in
its own module; nothing about pairing/authorization changes when it does,
since an adapter only ever acts on a device that has already completed
the full lifecycle above.

## The only device that exists today

`app/services/mock_iot.py`'s single mock AC — clearly labeled as mock-only
in its own docstring, in-memory state, no real network/hardware access.
It still goes through the real `DevicePairingService` permission check —
only the "does a command reach a physical device" step is mocked.

## Testing IoT today

Attempt to control an unpaired device -> denied, with a clear reason
(matches the task's Test 9 acceptance criterion exactly — verified live
in `tests/unit/test_subsystem_health.py::TestIoTStatus` and
`tests/integration/test_system_subsystem_status.py`). Pair the mock AC
through the real `/devices` API lifecycle, grant a permission, and
`/system`'s `iot` field switches to `CONNECTED` — confirmed live this
activation.
