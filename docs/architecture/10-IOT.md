# 10 — IoT Architecture

## 1. Principle

No device is controllable until it has completed the full trust flow:

```
PAIR → IDENTIFY → AUTHENTICATE → AUTHORIZE → REGISTER CAPABILITIES → CONTROL
```

This mirrors the Matter (Connectivity Standards Alliance) commissioning
model's shape (`docs/research/01-LANDSCAPE.md` §2.12) — VEYRA does not
invent a novel device trust model, it adopts the pattern proven by the
mature smart-home ecosystems studied in research, applied to VEYRA's own
device registry.

## 2. Data model

```
Device            id, name, type (DeviceType), connection_info,
                  trust_status (UNPAIRED|PAIRING|PAIRED|REVOKED),
                  last_seen_at
DeviceType        AC | Fan | TV | Refrigerator | Light | SmartPlug |
                  Speaker | Other
DeviceCapability  device_id, capability_key (e.g. "power", "brightness"),
                  value_schema
Connection        device_id, protocol (Matter|MQTT|LocalHTTP|Bluetooth|
                  VendorAPI), address, credentials_ref (never raw secrets —
                  see docs/security/05-DATA-PROTECTION.md)
DevicePermission  device_id, capability_key, granted_at, expires_at,
                  revoked_at
Command           device_id, capability_key, requested_value, issued_at,
                  result
```

## 3. Adapter interface (future; defined now)

```
DeviceGatewayAdapter (interface)
  discover() -> list[DiscoveredDevice]
  pair(device_id) -> PairingResult
  get_capabilities(device_id) -> list[DeviceCapability]
  send_command(device_id, capability_key, value) -> CommandResult
```

Concrete adapters (Matter, MQTT, local HTTP, Bluetooth, vendor APIs) all
implement this interface; the rest of the system never depends on a
protocol-specific detail.

## 4. Denial by default

Per the product brief §7 access boundary: IoT devices are DENIED BY DEFAULT.
A device only becomes reachable after explicit pairing and authorization —
there is no "discover and control automatically" behavior. `DevicePermission`
rows are required before any `Command` may be issued, checked by the same
Policy Engine used for all other tool calls (IoT commands are `SENSITIVE`
risk tier by default per the product brief §9 examples).

## 5. Phase 1 scope

Delivered: full data model, adapter interface, and the deny-by-default
policy wired into the Policy Engine's default rule set. Not delivered: any
protocol adapter implementation or real device — explicitly out of Phase 1
scope per the brief §39.

## 6. Phase 7 update — the flow is real, the device is still mock

`docs/phase-7/DEVICE-PAIRING.md` delivers a real, tested
`DevicePairingService` that enforces §1's six-stage flow procedurally
(a new `Device.pairing_stage` column makes "no stage skippable" an
enforced invariant, not just a comment) against a `MockACDevice` — no
real protocol adapter or discovery/network-scanning code exists yet, per
the brief's own Stop Condition. One deviation from §4 worth recording
honestly: the two mock control tools (`iot.mock_ac.set_power`/
`.set_temperature`) are registered as `RiskLevel.SAFE`, not `SENSITIVE`
— deliberately, so the generic Policy Engine step always passes through
immediately and the *device-specific* `DevicePermission` gate (checked
inside the executor via `DevicePairingService.is_permission_valid`) is
the layer actually under test, in isolation from the separate, already
well-tested `PermissionGrant` system. A real smart-home integration in a
future phase should likely use `SENSITIVE` and both layers together.
