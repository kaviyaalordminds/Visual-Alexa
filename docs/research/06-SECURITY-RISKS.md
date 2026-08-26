# 06 — Security Risks Observed in the Current Landscape

This document is the research-side companion to `docs/security/03-THREAT-MODEL.md`.
It summarizes risk classes that are *self-documented by frontier labs or
otherwise well evidenced*, which is why VEYRA treats them as certain rather
than speculative.

## 1. Prompt injection from on-screen / page content — CONFIRMED, self-documented
Both Anthropic's computer-use documentation and OpenAI's computer-use agent
system card explicitly warn that content the model observes (a web page, a
document, an email, OCR'd text) can contain instructions designed to hijack
the agent ("ignore previous instructions and..."). Both vendors ship
mitigations (isolating the browsing environment, confirmation requirements,
warnings against operating over untrusted content). This is the strongest
piece of external validation in this entire research effort: two competing
frontier labs independently converged on the same risk and the same general
mitigation shape (treat observed content as data, not instructions; require
confirmation for consequential actions).
**VEYRA response**: `docs/security/07-PROMPT-INJECTION.md`.

## 2. Over-broad agent access to the host machine — CONFIRMED via mitigation choice
Anthropic's own recommendation to run computer use inside a dedicated VM
rather than a production machine is itself evidence that the natural
integration (agent = full user-level access) is considered too risky for
general use by the vendor that ships the capability.
**VEYRA response**: capability-based, tool-scoped permissions
(`docs/security/02-PERMISSION-MODEL.md`) so the *agent's* access is bounded
regardless of what account it runs under.

## 3. Under-confirmation of consequential/destructive actions — CONFIRMED, retrofitted
Both vendors added confirmation requirements/"watch mode" for sensitive
actions after initial capability release, i.e., this was not the initial
default design — it was added because the initial default was judged
insufficient.
**VEYRA response**: risk tiers with CRITICAL actions requiring explicit
confirmation are part of the initial design, not a retrofit
(`docs/security/08-SENSITIVE-ACTION-POLICY.md`).

## 4. Credential/OTP/CAPTCHA exposure — OPEN QUESTION, treated as out of scope
No surveyed product publishes a clear, safe pattern for agents handling
login/OTP/CAPTCHA flows; this interacts with third-party ToS and account
security in ways well beyond Phase 1 scope.
**VEYRA response**: explicitly excluded from Phase 1 and flagged as an area
requiring dedicated security review before any future implementation
(`docs/security/01-SECURITY-ARCHITECTURE.md`).

## 5. Hidden/ambient sensing (always-on mic or screen capture) — industry-wide concern
Ambient/always-listening voice hardware and screen-sharing "vision" features
raise an inherent continuous-observation privacy question; mitigations vary
by vendor and are not uniformly documented.
**VEYRA response**: microphone and screen observation are OFF by default and
require explicit, visible enablement (`docs/security/05-DATA-PROTECTION.md`,
product brief §29).

## 6. No universal capability-based permission model for agent tool use — DESIGN INFERENCE
Absence of published detail is not proof of absence, but no surveyed product
documents a general, per-action, expiring, revocable permission grant for
agent tool calls comparable to mobile OS app permissions.
**VEYRA response**: `PermissionRequest`/`PermissionGrant` model
(`docs/security/02-PERMISSION-MODEL.md`).

## 7. Weak/undocumented auditability — OPEN QUESTION
Same caveat as above; treated as an opportunity regardless
(`docs/security/06-AUDIT-LOGGING.md`).

## Summary table

| Risk | Evidence strength | VEYRA mitigation doc |
|---|---|---|
| Prompt injection from observed content | Confirmed, self-documented by 2 labs | `docs/security/07-PROMPT-INJECTION.md` |
| Over-broad host access | Confirmed via mitigation choice | `docs/security/02-PERMISSION-MODEL.md` |
| Under-confirmation of risky actions | Confirmed, retrofitted by 2 labs | `docs/security/08-SENSITIVE-ACTION-POLICY.md` |
| Credential/OTP/CAPTCHA handling | Open question | Excluded from Phase 1 |
| Hidden ambient sensing | Industry-wide concern | `docs/security/05-DATA-PROTECTION.md` |
| No capability-based permissions | Design inference | `docs/security/02-PERMISSION-MODEL.md` |
| Weak auditability | Open question | `docs/security/06-AUDIT-LOGGING.md` |
