"""Dynamic tool discovery. docs/phase-7/TOOL-DISCOVERY.md, brief §26-27/
§158: a planner should not receive every tool definition on every
request — this is the real, tested narrowing primitive, built ahead of
the LLM-driven planner that will eventually call it (Phase 4's
`TaskPlanner` is a deterministic rule-based mapper today, not a
tool-calling LLM — see docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md §1).

Pure, deterministic substring matching over `id`/`name`/`description`/
`keywords` — no fuzzy scoring, no ranking model. Good enough to narrow
hundreds of tools down to a handful for a single natural-language-ish
query, and trivially fast (a linear scan) even at the "hundreds of
registered tools" scale brief §158 asks to load-test.
"""

from __future__ import annotations

from veyra_contracts.enums import ToolCategory
from veyra_contracts.tools import ToolDefinition


def search_tools(
    tools: list[ToolDefinition],
    *,
    query: str | None = None,
    category: ToolCategory | None = None,
) -> list[ToolDefinition]:
    results = tools
    if category is not None:
        results = [t for t in results if t.category == category]
    if query:
        needle = query.strip().lower()
        if needle:
            results = [t for t in results if needle in _haystack(t)]
    return results


def _haystack(tool: ToolDefinition) -> str:
    return " ".join([tool.id, tool.name, tool.description, *tool.keywords]).lower()
