# 08 — Sensitive Action Policy

## 1. Risk tiers (product brief §9, normative)

| Tier | Definition | Examples | Confirmation requirement |
|---|---|---|---|
| `SAFE` | Read-only or fully reversible, no side effects on user data/state | Read system status, search files, open application, open website | None (still policy-checked and audited) |
| `MODERATE` | Reversible side effects, low blast radius | Create folder, rename file, move file, edit document | Configurable — default: `ALLOW_SESSION` after first approval |
| `SENSITIVE` | Externally visible or harder-to-reverse effects | Send email, send message, send file, install application, control IoT device | Configurable per user preference; default requires confirmation, may be relaxed to `ALWAYS_ALLOW` per-tool by explicit user choice |
| `CRITICAL` | Destructive, irreversible, or high-privilege | Delete file, administrative command, system configuration change, run an unknown/unverified executable, run a script identified as dangerous | **Always** requires explicit, fresh confirmation — no stored grant, including `ALWAYS_ALLOW`, satisfies a CRITICAL check |

## 2. Why CRITICAL cannot be pre-authorized

This is the direct architectural response to
`docs/research/03-COMPETITOR-WEAKNESSES.md` item 8 (under-confirmation of
consequential actions, which both Anthropic and OpenAI had to retrofit
mitigations for after initial release). VEYRA makes it structurally
impossible to pre-authorize a CRITICAL action: the Policy Engine's decision
rule (`02-PERMISSION-MODEL.md` §3) special-cases `risk_level == CRITICAL` to
always require a new `PermissionRequest` with a real-time
`user_decision`, regardless of any existing `PermissionGrant`.

## 3. Confirmation UX contract

`PermissionRequest` (full schema in `02-PERMISSION-MODEL.md`) must present,
verbatim and un-paraphrased by the model: the exact tool/action, the exact
target, the risk tier, and a plain-language reason. Supported decisions:
`ALLOW_ONCE`, `ALLOW_FOR_SESSION` (MODERATE/SENSITIVE only), `ALWAYS_ALLOW`
(MODERATE/SENSITIVE only), `DENY`, `CANCEL`.

## 4. Revocability

Every grant, of any tier, is revocable at any time via `/permissions`
(`02-PERMISSION-MODEL.md`). Revocation takes effect immediately.

## 5. Phase 1 scope

Delivered: the tier enum, the CRITICAL-always-confirms rule enforced in the
Policy Engine and covered by unit tests (including a test that an
`ALWAYS_ALLOW` grant does **not** satisfy a CRITICAL check), and the
`PermissionRequest`/`PermissionGrant` API contract. Not delivered: any real
CRITICAL-tier tool (Phase 1's only registered tool is SAFE tier) or a
built confirmation UI beyond the API contract — the desktop shell's Phase 1
UI has no permission-prompt screen yet (nothing in Phase 1 can trigger one).
