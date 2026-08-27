# Tool Discovery

## 1. The problem, and why it isn't urgent yet

Brief §26-27/§158: a planner should not receive every tool's full
definition on every request — at 50 tools this is a mild inefficiency,
at "hundreds" (brief §158's own load-test framing) it becomes a real
prompt-size and latency problem for any LLM-driven planner.

`docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md` §1 found that this problem
doesn't actually exist yet in this codebase: `TaskPlanner`
(`app/services/agent/planner.py`) is a deterministic, rule-based
intent-to-plan mapper — it never constructs a prompt containing tool
definitions, and `ToolSelector.select()` only rejects an already-chosen
tool id that turns out not to exist (guarding against a hallucinated
tool, not narrowing a catalog). There is no live caller today that
would benefit from narrowing.

This phase builds the primitive anyway, ahead of the LLM-driven planner
that will eventually need it, so a future phase can wire it in without
first inventing and testing the narrowing logic under time pressure.

## 2. `search_tools`

`veyra_contracts.discovery.search_tools(tools, *, query=None,
category=None)` — a pure function, deterministic substring matching over
`id`/`name`/`description`/`keywords` (case-insensitive), with an
optional `category` filter applied first. No fuzzy scoring, no ranking
model — good enough to narrow hundreds of tools down to a handful for a
single query, and fast (`tests/unit/test_tool_discovery.py`'s own
500-tool scale test asserts well under 100ms).

`ToolDefinition.keywords: list[str]` is a new, additive field (empty by
default — none of the 50 tools registered before this phase set it)
callers can populate for better recall; matching also falls back to
`id`/`name`/`description` even with no keywords set.

## 3. Wiring

`GET /tools?query=...&category=...` (`app/api/tools.py`) is the one real
caller today — `search_tools(tool_registry.list(category=category),
query=query)`. Verified against the real, live 50+-tool registry in
`tests/integration/test_tools_api.py` (not a fake catalog).

## 4. What this is not

Not a replacement for `ToolSelector`'s hallucination guard (unchanged,
still the thing that rejects a tool id that doesn't exist once a plan
has already chosen one). Not an LLM-facing prompt-construction helper —
no such prompt exists yet to construct. Not a ranking/relevance model —
plain substring matching, deliberately simple and fully deterministic.
