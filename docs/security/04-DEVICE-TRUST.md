# 04 — Device Trust Model

## 1. Access boundary (product brief §7, normative)

```
INSTALLED WINDOWS PC   → PRIMARY ENVIRONMENT (trusted, default)
OTHER PC                 → DENIED BY DEFAULT
PHONE                      → DENIED BY DEFAULT
TABLET                       → DENIED BY DEFAULT
IOT DEVICE                     → DENIED BY DEFAULT
REMOTE ACCESS                    → DISABLED BY DEFAULT
INTERNET                           → WEB ACCESS ONLY (does not imply
                                    access to another computer or device)
```

Internet connectivity is never treated as equivalent to device access.
These are two independent permissions in the data model — a device having
network reachability does not grant it a `DevicePermission` row.

## 2. Trust flow (all six stages required, in order, no shortcuts)

```
1. PAIR         — device is discovered and a pairing handshake initiated
2. IDENTIFY      — device reports identity (type, vendor, unique id)
3. AUTHENTICATE   — device/user proves identity (protocol-specific: Matter
                    commissioning, MQTT credentials, vendor OAuth, etc.)
4. AUTHORIZE       — user explicitly grants VEYRA permission to control
                    this specific device
5. REGISTER          — device's actual capabilities are enumerated and
   CAPABILITIES        stored (`DeviceCapability` rows) — VEYRA never
                    assumes capabilities it hasn't confirmed
6. CONTROL             — only now can a `Command` be issued, still subject
                    to the same Policy Engine check as any other tool call
```

Skipping a stage is not possible by construction: `Command` issuance
requires a `DevicePermission` row, which requires stage 4 to have completed,
which requires stages 1–3 to have produced a `Device` row with
`trust_status = PAIRED`.

## 3. Revocation

Any `DevicePermission` can be revoked by the user at any time; a revoked
device immediately loses `CONTROL` stage access (checked at command time).
Un-pairing a device cascades to revoke all its `DevicePermission` rows.

## 4. Relationship to `10-IOT.md`

This document defines the trust *policy*; `docs/architecture/10-IOT.md`
defines the *data model and adapter interfaces* that implement it. They are
kept separate so the security policy can be reviewed independent of protocol
implementation detail.

## 5. Phase 1 scope

Delivered: full data model + the deny-by-default enforcement path in the
Policy Engine (verified by unit tests asserting a `Command` is rejected
without a completed trust flow). Not delivered: any real pairing protocol
implementation.
