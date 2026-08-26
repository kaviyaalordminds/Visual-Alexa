# Model Abstraction

`LLMProvider` (`app/services/agent/llm_provider.py`) — a `Protocol`
(`understand`, `plan`, `reason`, `summarize`, `classify`), mirroring Phase
3's `VisionProvider` precedent exactly.

## 1. No real provider ships in Phase 4

`NotConfiguredLLMProvider` is the only implementation. Every method
returns `LLMResult(available=False, reason="No LLM provider configured.")`
— never raises, never makes a network call. Brief §32: "If no model is
configured: the application must fail gracefully. Do not crash." Verified
structurally — this class has no imports beyond the standard library, so
there is nothing in it that *could* reach the network.

## 2. What actually works without a model

`IntentInterpreter` and `TaskPlanner` (see `INTENT.md`, `PLANNER.md`) are
deterministic, rule-based, and never call `LLMProvider` at all — this is
Phase 4's genuinely functional, no-model-required path, directly
satisfying brief §32's "basic tasks should eventually work without
internet... intent classification, simple planning... structured
transformation." A future real provider slots in *underneath* this
Protocol without changing the orchestrator's control flow.

## 3. Provider independence (CLAUDE.md)

"No vendor-specific AI SDK may be imported outside its designated
provider adapter module" — there is no vendor SDK imported anywhere in
`app/services/agent/`; a future local/OpenAI-compatible/Anthropic-compatible/
Gemini provider would live in its own adapter module implementing this
Protocol, never imported from the orchestrator directly.

## 4. Structured output discipline (brief §35-36)

Not yet exercised against a real model (none exists), but the contract is
in place: `LLMResult` is a plain, typed container; nothing in the
orchestrator ever treats free-form text from an `LLMResult.content` field
as an executable instruction — the only things that ever become
`ToolCallRequest`s are `PlanStep`s produced by `TaskPlanner`, which are
themselves pydantic-validated (`veyra_contracts.PlanStep`) before use.
