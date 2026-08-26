# 03 — AI Architecture

## 1. Modes

VEYRA defines three AI modes as a first-class configuration axis, not an
afterthought:

| Mode | Reasoning | Tools | Data control |
|---|---|---|---|
| LOCAL | Local model (future: llama.cpp/ONNX-class runtime) | Local | Fully local |
| HYBRID | Cloud model for reasoning | Local | Local security/data boundary maintained; only the minimum necessary context is sent to the cloud provider, never raw credentials or unrelated files |
| CLOUD | Cloud model | Local | Explicitly opt-in |

Phase 1 ships the `AIProvider` interface and configuration surface only;
`AI: NOT CONFIGURED` is a valid, supported system state (see `apps/desktop`
status screen and `/system` endpoint) — no model is wired in.

## 2. Provider independence

```
Planner / ConversationManager
        │
        ▼
   AIProvider (interface)
        │
   ┌────┴─────┬──────────────┬────────────┐
   ▼           ▼              ▼            ▼
LocalModel   AnthropicProvider  OpenAIProvider  <future providers>
Provider     (HYBRID/CLOUD)     (HYBRID/CLOUD)
(LOCAL)
```

No module outside `services/ai-runtime`'s provider adapters may import a
specific vendor SDK. The rest of the system talks to `AIProvider` only. This
is enforced by code review / lint boundary in later phases; Phase 1 defines
the interface (`packages/contracts`) so it exists before any provider is
implemented.

## 3. The model never gets raw OS access

The `AIProvider` interface's only output type is a `PlannedAction` or
`ToolCallRequest` — a structured, schema-validated object naming a tool ID
and arguments. There is no code path from a model response to `exec()`,
`subprocess`, PowerShell, or direct file I/O. Every `ToolCallRequest` is
submitted to the Policy Engine before the Tool Executor ever sees it (see
`docs/security/01-SECURITY-ARCHITECTURE.md`).

## 4. Reasoning loop (future; contract defined now)

```
OBSERVE  → gather context (conversation, memory, current task state,
           relevant UI evidence per 05-COMPUTER-CONTROL.md)
PLAN     → AIProvider proposes next step(s) as ToolCallRequest(s)
POLICY   → Policy Engine checks permission + risk tier
ACT      → Tool Executor runs the tool (Phase 1: stub only)
OBSERVE  → re-gather evidence
VERIFY   → tool-specific verification strategy confirms expected outcome
RECOVER  → on failure: retry / replan / ask user / fail safely, bounded by
           TaskRuntime budget (max steps, timeout — see 14-TASK-LIFECYCLE.md)
```

## 5. Confidence-aware execution

Every `PlannedAction` carries a `confidence` field:

- `HIGH` → eligible for direct execution (subject to policy/risk checks)
- `MEDIUM` → planner must gather more evidence or ask a clarifying question
  before proceeding
- `LOW` → planner must ask the user
- Regardless of confidence, any action whose tool `risk_level` is `CRITICAL`
  requires explicit user confirmation (see
  `docs/security/08-SENSITIVE-ACTION-POLICY.md`) — confidence never
  overrides risk tier.

## 6. Ambiguity resolution contract

Before planning a tool call whose target could resolve to more than one
concrete entity (a contact, a file, a device), the planner must run an
`AmbiguityCheck`. If more than one candidate is found, the planner emits a
clarifying question instead of a tool call. This is a hard contract, tested
by `tests/agent-evals` fixtures (Phase 1 ships one worked fixture as a
specification; no live planner exists yet to execute it against).

## 7. Phase 1 scope boundary

Delivered: mode configuration, `ToolCallRequest` contract, confidence
enum, ambiguity-check contract (`resolve_ambiguity`). Not delivered:
`AIProvider`/`PlannedAction` as described above were never actually
implemented in code — Phase 4 re-verified this by direct inspection
(`docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md` §1) and built the real
equivalent under different, now-implemented names — see §8.

## 8. Phase 4: the real planning/execution loop

`docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md` and
`docs/phase-4/AGENT-ARCHITECTURE.md` deliver the loop this section
sketched, for real: `IntentInterpreter` (deterministic, not a model —
`docs/phase-4/INTENT.md`) replaces the unbuilt `AIProvider.understand`;
`TaskPlanner`+`ToolSelector` (`docs/phase-4/PLANNER.md`,
`TOOL-SELECTION.md`) replace `PlannedAction`; `LLMProvider`
(`docs/phase-4/MODEL-ABSTRACTION.md`) is the actual provider-independence
interface this section described, with only `NotConfiguredLLMProvider`
shipped. The confidence-aware execution policy (§5 above) and the
ambiguity-resolution contract (§6 above) are both now exercised by a real
caller (`TaskPlanner`) for the first time, not merely modeled — see
`docs/phase-4/PHASE-4-TEST-RESULTS.md`.
