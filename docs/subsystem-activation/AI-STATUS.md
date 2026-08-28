# AI Subsystem Status

**Current status in this environment: NOT CONFIGURED**
Reason: no `VEYRA_AI_PROVIDER`/`VEYRA_AI_MODEL`/`VEYRA_AI_API_KEY`/
`VEYRA_AI_BASE_URL` are set.

## Architecture

```
VEYRA -> Local API -> AI Runtime (app/services/agent/) -> LLMProvider -> Response
```

`LLMProvider` (`app/services/agent/llm_provider.py`) is a real `Protocol`
with two implementations: `NotConfiguredLLMProvider` (fails gracefully,
never raises, never makes a network call — the default) and
`CloudLLMProvider` (`app/services/agent/providers.py`, new this
activation) — a generic OpenAI-compatible HTTP client using `httpx`, no
vendor SDK imported anywhere. Which one is active is a pure runtime
config decision (`build_llm_provider(settings)`), never hard-coded.

## How to configure a real provider

Set all four in your `.env` (never commit it):

```
VEYRA_AI_PROVIDER=openai-compatible
VEYRA_AI_MODEL=gpt-4o-mini            # or whatever your provider serves
VEYRA_AI_API_KEY=sk-...
VEYRA_AI_BASE_URL=https://api.openai.com/v1
```

This works for OpenAI itself, most OpenAI-compatible cloud providers, and
a local Ollama/LM Studio-style server (point `VEYRA_AI_BASE_URL` at it,
e.g. `http://127.0.0.1:11434/v1`).

## The two-tier health check

- **Passive** (`GET /system`'s `ai` field): configuration-presence only,
  never a network call on every 5-second poll (that would be wasteful and
  potentially billable on every UI refresh). Reports `DEGRADED` once
  configured but not yet tested.
- **Active** (`system.ai_health_check` tool, `POST
  /tools/system.ai_health_check/invoke`): a real, cheap `GET
  {base_url}/models` reachability probe (no inference call, no per-token
  cost). Updates the cache `/system`'s passive check then reads —
  `CONNECTED` after a real success, `ERROR` with the real reason after a
  real failure.

The API key is never returned by any endpoint, never logged, and never
appears in an `AuditLog` row — confirmed by
`tests/integration/test_subsystem_diagnostic_tools.py`.

## What this activation did NOT do

Wire `CloudLLMProvider` into the planner (`TaskPlanner`/`ModelRouter`
remain deterministic, unchanged) — general LLM-backed planning is a
distinct, larger future phase per `docs/PHASE-9-AUDIT.md`'s own finding
that `ModelRouter.route()` always returns `"deterministic"` today, by
design. This activation makes the *connectivity layer* real and
observable; it does not change what the assistant can actually plan.
