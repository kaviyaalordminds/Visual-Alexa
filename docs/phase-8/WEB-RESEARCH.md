# Web Research / Comparison

## 1. One tool, one bounded loop, no second agent framework

Brief §98: "It must use existing Phase 4 agent infrastructure. Do NOT
create a second unrelated agent framework." `WebResearchAgent.run()`
(`research.py`) is not a second `AgentOrchestrator` — it is the internal
implementation of the one `web.research` tool (`tools.py`), itself just
another entry in the same `ToolRegistry` Phase 4's real orchestrator
already calls through. The bounded PLAN→SEARCH→SELECT→OPEN→OBSERVE→
EXTRACT→EVALUATE→COMPARE→SYNTHESIZE loop (brief §34) lives entirely
inside this one tool call.

## 2. The loop, concretely

1. **PLAN/SEARCH** — the goal text becomes a Google search query directly
   (no LLM call invented for query rewriting this phase — honest, simple,
   real).
2. **SELECT** — `SourceRanker.rank()`: real link extraction
   (`adapter.list_links()`), excludes the search engine's own domain,
   deduplicates by domain, unwraps Google's `/url?q=...` redirect wrapper
   (a real, useful piece of "don't blindly trust SEO ranking," brief
   §102), and prefers links whose anchor text overlaps the query.
3. **OPEN** — up to `min(max_sites, max_tabs)` new tabs, each bounded by
   `max_steps`/`max_time_seconds`.
4. **OBSERVE/EXTRACT** — `ContentExtractor`: real visible-text extraction,
   sanitized (`WebContentSanitizer`), capped to 1500 chars per source.
5. **EVALUATE** — each source gets a `quality` tag (`official` for
   `.gov`/`.edu`, `secondary` for known reference domains like Wikipedia,
   `unknown` otherwise) — a real, honest first line, never a claim of
   deep source-authority modeling.
6. **COMPARE** — `ComparisonEngine`: lexical word-frequency overlap across
   sources. `similarities` = words appearing in ≥2 sources; `differences`
   = each source's uniquely-mentioned words. `normalized_fields` is left
   empty and documented as such — real structured field extraction (price,
   spec tables, ...) needs domain-specific parsing this phase doesn't
   build (brief §171 "do not overbuild").
7. **SYNTHESIZE** — a real, honest one-paragraph `summary` built from the
   actual source count/domains/similarities — never a fabricated claim of
   deeper analysis than what was actually computed.

## 3. Budgets (brief §99)

`max_sites`, `max_tabs`, `max_steps`, `max_time_seconds` — all real,
checked on every iteration (`_budget_ok()`), never an unbounded loop. A
budget exceeded mid-loop stops gracefully and returns whatever sources
were already gathered (a partial result is still useful); zero sources
gathered at all raises `ResearchBudgetExceeded` -> `ErrorCategory.TIMEOUT`,
a real, honest failure rather than fabricating a result
(`tests/integration/test_browser_tools_api.py::
test_web_research_returns_sources_and_summary` proves this against the
fake adapter with nothing seeded).

## 4. Source citations (brief §101)

Every `ResearchSource` retains `url`/`domain`/`title`/`retrieved_at` — the
final `ResearchResult.sources` list is the one place a caller/UI gets
"where did this come from," never dropped after synthesis.

## 5. What's not delivered

No query refinement loop (brief §103 — "poor results -> rewrite query ->
better results") — one query per research task this phase. No web table
extraction into structured objects (brief §106) beyond what plain text
extraction already surfaces. No parallel-tab fan-out beyond the sequential
`max_tabs` bound (brief §134's "carefully... never create uncontrolled
browser storms" is honored by never exceeding that bound, not by true
concurrency).
