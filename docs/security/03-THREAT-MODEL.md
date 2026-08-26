# 03 — Threat Model

Companion to `docs/research/06-SECURITY-RISKS.md` (research-side evidence);
this document is the design-side response.

## 1. Assets

- User's files and file system
- User's credentials (never directly handled by VEYRA in Phase 1+ scope)
- User's applications and their data
- User's conversation history and memory records
- Paired external devices
- The Local API and database themselves (integrity of VEYRA's own state)

## 2. Adversaries / threat sources

| Threat source | Description |
|---|---|
| Malicious/compromised on-screen or page content | A web page, document, email, or OCR'd text containing instructions designed to hijack the agent (prompt injection) |
| A misbehaving or hallucinating model | Model proposes an incorrect or dangerous tool call without malicious intent |
| A malicious local process | Another process on the same machine attempting to reach the Local API |
| A malicious/unauthorized network peer | Attempting to reach the Local API or a paired device over the network |
| Social engineering of the user | User tricked into approving a permission they shouldn't |
| Supply chain | Compromised dependency in `packages/`, `services/`, or `apps/` |

## 3. Threats and mitigations

| # | Threat | Mitigation | Doc |
|---|---|---|---|
| T1 | Prompt injection from untrusted observed content leads to unintended tool calls | Content is data, never instructions; Policy Engine still enforces risk tier/permission regardless of what the model claims the content told it to do | `07-PROMPT-INJECTION.md` |
| T2 | Model requests an over-broad or destructive action | Policy Engine risk-tier + permission check on every call, independent of model intent; CRITICAL always requires fresh confirmation | `02-PERMISSION-MODEL.md`, `08-SENSITIVE-ACTION-POLICY.md` |
| T3 | Local process impersonates the desktop shell and calls the Local API directly | Local API binds to loopback only in Phase 1; future phases add a shared local auth token between shell and API (documented as required before any non-loopback exposure) | `01-SECURITY-ARCHITECTURE.md` |
| T4 | Network peer reaches the Local API | Local API never binds to a non-loopback interface by default; no remote access surface exists in Phase 1 | `01-SECURITY-ARCHITECTURE.md`, product brief §7 |
| T5 | Unauthorized device control | Deny-by-default device trust model; pairing required before any `Command` | `04-DEVICE-TRUST.md` |
| T6 | Credential exposure via logs/audit trail | Audit log schema explicitly excludes raw credential fields; secrets are referenced (`credentials_ref`), never stored/logged in plaintext | `05-DATA-PROTECTION.md`, `06-AUDIT-LOGGING.md` |
| T7 | Compromised dependency introduces malicious code | Dependency rules in `CLAUDE.md` (minimal, reviewed dependencies; no unnecessary additions); Phase 1 dependency set is deliberately small | `CLAUDE.md` |
| T8 | User approves a permission via social engineering (misleading `reason` text) | `PermissionRequest.reason` is generated from the actual tool/target, not free-form model text the model fully controls; risk tier and target are always shown verbatim, not paraphrased | `02-PERMISSION-MODEL.md` |
| T9 | Database tampering (a local process edits SQLite directly, bypassing the API) | Out of scope to fully prevent (an attacker with local disk write access already has significant capability); mitigated by keeping the database file under the user's own profile permissions and documenting this as a known limitation, not a false guarantee | This document, §5 |

## 4. Non-goals (explicitly not defended against in Phase 1)

- A fully compromised OS (if the attacker already has arbitrary code
  execution as the user, VEYRA cannot provide guarantees beyond what any
  local application can).
- Nation-state-level physical access attacks.
- CAPTCHA/anti-automation defeat (explicitly excluded, see product brief).

## 5. Known limitation

Phase 1's Local API has no authentication token yet (loopback-only binding
is the sole current network boundary). This is acceptable because there is
no non-loopback exposure and no remote access surface, but **must** be
addressed (shared-secret or OS-level IPC auth) before any future phase adds
network exposure beyond loopback. Flagged explicitly in the final report's
"architectural risks" section.
