# 01 — Security Architecture

## 1. The core chain

```
USER
 ↓
VOICE / TEXT
 ↓
INTENT
 ↓
PLANNER              (proposes ToolCallRequest; cannot execute anything)
 ↓
POLICY ENGINE        (checks risk tier + PermissionGrant; can reject/require
 ↓                    confirmation; this is the enforcement point)
TOOL REGISTRY         (resolves the tool definition; unknown tool = reject)
 ↓
TOOL EXECUTOR          (performs the action; Phase 1 = stubs only)
 ↓
TARGET
 ↓
VERIFICATION             (confirms expected postcondition)
 ↓
AUDIT LOG                  (always written, success or failure)
 ↓
USER
```

## 2. The load-bearing rule

**The LLM never directly receives unrestricted OS access.** Every arrow from
PLANNER onward is code, not model output. The model can only ever produce a
`ToolCallRequest` — a schema-validated, typed object naming a registered
tool ID and arguments. There is no code path from a model's raw text/tool
output to `exec()`, shell invocation, PowerShell, unrestricted filesystem
writes, or unrestricted deletion.

This is not a policy the model is asked to follow — it is a structural fact
about which functions exist and what can call them. A prompt-injected or
misbehaving model can *request* anything; it cannot *bypass* the Policy
Engine, because the Policy Engine sits in code between the planner and the
executor for every single tool call, with no alternate path.

## 3. Explicit prohibitions (Phase 1 and beyond, absolute)

- No arbitrary shell execution from model-originated input.
- No arbitrary PowerShell execution from model-originated input.
- No unrestricted filesystem writes (writes are scoped to specific,
  policy-checked tool calls with validated targets).
- No unrestricted deletion (delete operations are `CRITICAL` risk tier,
  always require explicit confirmation — see `08-SENSITIVE-ACTION-POLICY.md`).
- No silent remote-device access (see `04-DEVICE-TRUST.md` — deny by
  default, explicit pairing required).
- No credential extraction (VEYRA never reads, logs, or exfiltrates stored
  credentials; the Phase 1 scope has no credential-handling tools at all).
- No hidden background actions (every tool execution is audited and, for
  SENSITIVE/CRITICAL tiers, requires a visible permission decision).

## 4. Explicitly out of Phase 1 scope

Full computer control, full voice, full vision, WhatsApp automation, IoT
drivers, autonomous destructive operations, remote access — per the product
brief §39. This document defines the security chain those future
capabilities must be built inside; it does not implement them.

## 5. What must NOT change without architectural review

- The Policy Engine may never be bypassed for any tool category, including
  future first-party ("trusted") tools.
- No component other than the Local API's Policy Engine may issue a
  `PermissionGrant` or make a risk-tier decision.
- No tool executor may be registered without passing through
  `ToolRegistry.register()`, which validates the presence of `risk_level`
  and `required_permission`.
