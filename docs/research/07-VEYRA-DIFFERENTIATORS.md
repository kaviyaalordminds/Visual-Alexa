# 07 — VEYRA Differentiators

VEYRA does not claim to be better because it has more features. This
document defines measurable, architectural differentiators — each grounded
in a specific gap identified in `03-COMPETITOR-WEAKNESSES.md` and
`06-SECURITY-RISKS.md` — with a stated problem, the existing landscape
approach, VEYRA's approach, the technical design, how it will be measured,
and what Phase 1 actually delivers versus what is future work.

## 1. Structured tool execution (LLM never touches the OS directly)
- **Problem**: general-purpose computer-use capabilities let the model's
  output (a coordinate, a shell string) become the action directly, or close
  to it.
- **Existing approach**: screenshot → model emits coordinates/keystrokes →
  executed by a thin actuator layer with limited independent policy checking.
- **VEYRA approach**: every action goes through a typed Tool Registry; the
  model can only ever request a *named tool call with a validated schema*,
  never raw OS primitives.
- **Technical design**: `docs/architecture/04-TOOL-ARCHITECTURE.md`,
  `packages/contracts`.
- **Measurement**: 100% of executed actions traceable to a registered
  `ToolDefinition` with schema-validated input; zero code paths allow
  arbitrary shell/PowerShell execution from model output (verified by
  `tests/security`).
- **Phase 1 delivers**: the contracts, registry data model, and policy-check
  interfaces (stubbed executors only — no tool performs real OS actions yet).

## 2. Capability-based permissions
- **Problem**: documented mitigation for over-broad access is "run in a
  throwaway VM," not "scope the agent's own permissions."
- **VEYRA approach**: `PermissionGrant` records scope exactly which tool,
  target, and risk tier are authorized, with expiration and revocation,
  independent of what OS account VEYRA runs under.
- **Technical design**: `docs/security/02-PERMISSION-MODEL.md`.
- **Measurement**: every SENSITIVE/CRITICAL tool call is rejected by the
  Policy Engine unless a matching, unexpired `PermissionGrant` exists —
  enforced by a database constraint + policy engine unit tests, not by
  convention.
- **Phase 1 delivers**: full data model + policy engine interface + tests;
  no real sensitive tools exist yet to exercise it against.

## 3. Local-first execution
- **Problem**: every surveyed conversational assistant requires cloud
  round-trips for core reasoning.
- **VEYRA approach**: the installed PC is the default, primary environment;
  LOCAL / HYBRID / CLOUD modes are a first-class architectural axis.
- **Technical design**: `docs/architecture/03-AI-ARCHITECTURE.md`.
- **Measurement**: local API, database, and tool registry function fully
  with zero outbound network calls (verified: Phase 1's local-api test suite
  runs with network egress disabled).
- **Phase 1 delivers**: local API + local SQLite database + settings
  indicating AI mode; no LLM is wired in yet (explicitly out of scope).

## 4. Explicit external-device trust
- **Problem**: general computer-use agents have zero IoT surface; where IoT
  does exist (Alexa/Google/HomeKit), the trust model is good but is a
  vertical silo, not something a general assistant's *action layer* is
  bound by.
- **VEYRA approach**: no device (PC, phone, IoT) is reachable until it
  completes pair → identify → authenticate → authorize → register
  capabilities → control, mirroring Matter's commissioning shape.
- **Technical design**: `docs/security/04-DEVICE-TRUST.md`,
  `docs/architecture/10-IOT.md`.
- **Phase 1 delivers**: data model (`Device`, `DeviceCapability`,
  `DevicePermission`) and denial-by-default policy; zero device drivers.

## 5. Multi-source UI understanding (evidence hierarchy)
- **Problem**: coordinate/screenshot grounding dominates despite documented
  fragility; structured alternatives (UIA/DOM) exist and are proven in
  narrower tools.
- **VEYRA approach**: native API → UI Automation → accessibility tree →
  app integration → browser DOM → OCR → vision model → coordinates, in that
  priority order, with the tier used recorded per action for auditability.
- **Technical design**: `docs/architecture/05-COMPUTER-CONTROL.md`,
  `docs/architecture/07-VISION.md`.
- **Phase 1 delivers**: the interface/enum defining the hierarchy and where
  it plugs into the tool/verification contracts; no controller
  implementations yet.

## 6. Observe → Plan → Policy Check → Act → Observe → Verify → Recover
- **Problem**: documented agent loops are largely flat act/re-observe loops
  without an explicit, host-visible state machine.
- **VEYRA approach**: task execution is a typed state machine
  (`docs/architecture/14-TASK-LIFECYCLE.md`) whose states drive UI/avatar
  state via the event bus.
- **Phase 1 delivers**: the state machine definition, transitions, and unit
  tests; no autonomous planner wired to it yet.

## 7. Task recovery
- **Problem**: no surveyed product documents an explicit "diagnose why a
  step failed, then retry/replan/ask/fail-safely" contract.
- **VEYRA approach**: RECOVERING is a distinct task state with a bounded
  budget (max retries, timeout), never an unbounded retry loop.
- **Phase 1 delivers**: the state + budget fields in the task data model and
  state machine tests; no real recovery heuristics yet (would require real
  tools to recover from).

## 8. Ambiguity detection
- **Problem**: no general "ask, don't guess" contract documented across
  surveyed general-purpose agents.
- **VEYRA approach**: the planner contract requires an explicit
  `AmbiguityCheck` step before any tool call whose target could resolve to
  multiple entities; agent-eval tests assert this behavior.
- **Phase 1 delivers**: contract interface + one worked eval fixture
  ("send file to Arun" with two Aruns) documenting expected behavior; no
  live planner to run it against yet — the eval is written as a spec.

## 9. Confidence-aware action
- **Problem**: hallucinated UI elements from vision grounding are a known
  general VLM failure mode; no surveyed product documents an explicit
  confidence-to-behavior mapping.
- **VEYRA approach**: HIGH → execute, MEDIUM → inspect further/clarify,
  LOW → ask user, CRITICAL action → always confirm regardless of confidence.
- **Phase 1 delivers**: the confidence enum and policy-engine hook;
  no model integration to produce real confidence scores yet.

## 10. Persistent, user-controlled memory
- **Problem**: existing "memory" features are largely free-text
  personalization, not structured/typed/revocable records.
- **VEYRA approach**: seven distinct memory categories, all inspectable,
  editable, deletable; nothing hidden.
- **Phase 1 delivers**: full schema + CRUD API surface (contracts + DB
  tables); no automatic memory writing yet (would require a live agent).

## 11. Visual identity
- **Problem**: voice-only assistants have no embodied presence; the one
  visually-marked competitor (Copilot) has a brand mark, not a stateful
  character.
- **VEYRA approach**: an original avatar with an explicit state machine tied
  to task execution state (product brief §16).
- **Phase 1 delivers**: architecture doc only, per explicit Phase 1
  exclusion of final avatar assets.

## 12. Multilingual voice (English / Tamil / Tanglish)
- **Problem**: Tanglish conversational accuracy is an open question
  industry-wide; no pluggable architecture is documented for iterating on it
  independently of STT vendor choice.
- **VEYRA approach**: language detection is a distinct pipeline stage,
  decoupled from STT engine choice, decoupled from local-vs-cloud.
- **Phase 1 delivers**: architecture doc + interface stubs; no STT/TTS
  integration (explicitly excluded from Phase 1).

## 13. Provider independence
- **Problem**: every surveyed product is structurally coupled to one
  vendor's cloud AI.
- **VEYRA approach**: `AIProvider` is an interface, never a hard dependency;
  local, hybrid, and cloud modes are equally first-class.
- **Phase 1 delivers**: the interface and configuration surface (`AI:
  NOT CONFIGURED` is a legitimate, supported state, not an error).

## 14. Offline capability
- Same technical design as #3/#13; distinguished here because "local
  database + local tools" (offline-capable foundation) is delivered in
  Phase 1 even though "offline AI reasoning" is not (needs a local model,
  future phase).

## 15. Detailed, user-visible audit trail
- **Problem**: audit logging is largely undocumented/host-app-dependent
  across surveyed products.
- **VEYRA approach**: every tool execution writes a structured `AuditLog`
  row with correlation ID, permission checked, and outcome.
- **Phase 1 delivers**: schema + write path from the (stub) tool executor;
  no UI to browse it yet beyond the API contract.

## 16. Modular integrations
- **Problem**: assistants bundle first-party integrations tightly; VEYRA
  needs email/WhatsApp/media/etc. to be swappable adapters, not core-coupled.
- **VEYRA approach**: `integrations/` adapter interfaces, official-API-only,
  OAuth-based.
- **Phase 1 delivers**: directory structure + interface stubs only, zero
  live integrations (explicitly excluded).

## 17. Security boundaries independent of the LLM
- **Problem**: if the only thing preventing a destructive action is "the
  model decided not to," that is not a security boundary.
- **VEYRA approach**: the Policy Engine enforces risk tier and permission
  checks in code, outside the LLM's control, on every tool call — the model
  can *request* anything; it cannot *bypass* a check.
- **Phase 1 delivers**: this is the single most important Phase 1 principle
  and is reflected in every layer built (see `CLAUDE.md` "Never bypass
  security").
