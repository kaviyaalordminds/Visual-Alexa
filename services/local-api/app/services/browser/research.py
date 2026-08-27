"""WebResearchAgent / SourceRanker / ContentExtractor / ComparisonEngine.
docs/phase-8/WEB-RESEARCH.md, docs/phase-8/WEB-COMPARISON.md.

brief §98: "It must use existing Phase 4 agent infrastructure. Do NOT
create a second unrelated agent framework." This agent does not run a
second `AgentOrchestrator` — it is the internal implementation of the one
`web.research` tool (tools.py), itself just another entry in the same
`ToolRegistry` Phase 4's orchestrator already calls through. The bounded
PLAN->SEARCH->SELECT->OPEN->OBSERVE->EXTRACT->EVALUATE->COMPARE->
SYNTHESIZE loop (brief §34) lives entirely inside this one tool call.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

from veyra_contracts import ResearchResult, ResearchSource

from app.services.browser.manager import BrowserManager, domain_of
from app.services.browser.security import WebContentSanitizer

_OFFICIAL_TLDS = (".gov", ".edu")
_SECONDARY_DOMAINS = ("wikipedia.org",)

_STOPWORDS = frozenset(
    "the a an is are was were be been being of to in on for and or with as by at from this "
    "that it its into your you we our".split()
)


class ResearchBudgetExceeded(RuntimeError):
    """Raised only when the research task could gather zero usable
    sources at all within budget — a genuine failure, not the normal
    'stopped early because a limit was reached' case (which returns a
    partial, still-useful `ResearchResult` instead)."""


def _quality_of(domain: str) -> str:
    if any(domain.endswith(tld) for tld in _OFFICIAL_TLDS):
        return "official"
    if any(known in domain for known in _SECONDARY_DOMAINS):
        return "secondary"
    return "unknown"


class SourceRanker:
    """brief §102 — 'Do not blindly trust SEO ranking.' The one real
    signal available without a second search API: prefer links whose
    visible anchor text actually overlaps the query, over raw result
    order, and always drop links back to the search engine itself."""

    def rank(
        self, links: list[tuple[str, str]], *, exclude_domain: str, query: str, max_results: int
    ) -> list[str]:
        query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
        seen: set[str] = set()
        scored: list[tuple[float, str]] = []
        for text, href in links:
            url = self._unwrap_redirect(href)
            domain = domain_of(url)
            if not domain or domain == exclude_domain or domain in seen:
                continue
            seen.add(domain)
            text_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
            overlap = len(query_tokens & text_tokens)
            scored.append((float(overlap), url))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [url for _score, url in scored[:max_results]]

    def _unwrap_redirect(self, href: str) -> str:
        """Google's `/url?q=<target>&...` result-link wrapper — the one
        real redirect-unwrapping worth doing without a second HTTP call."""
        parts = urlsplit(href)
        if parts.path == "/url":
            target = parse_qs(parts.query).get("q")
            if target:
                return target[0]
        return href


class ContentExtractor:
    def __init__(self, sanitizer: WebContentSanitizer | None = None) -> None:
        self._sanitizer = sanitizer or WebContentSanitizer()

    async def extract(self, adapter, tab_ref: str) -> str:
        text = await adapter.get_visible_text(tab_ref, max_chars=3000)
        return self._sanitizer.sanitize(text, max_chars=1500)


class ComparisonEngine:
    """brief §107 — real, honest, and deliberately simple: lexical
    overlap across sources, never a fabricated structured-field
    extraction (that needs domain-specific parsing this phase doesn't
    build, per brief §171 'do not overbuild'). `normalized_fields` is
    left empty and documented as such rather than faked."""

    def compare(self, sources: list[ResearchSource]) -> tuple[dict, list[str], list[str]]:
        if len(sources) < 2:
            return {}, [], []

        per_source_words: list[set[str]] = []
        for source in sources:
            words = {
                w
                for w in re.findall(r"[a-z]{4,}", source.retrieved_content.lower())
                if w not in _STOPWORDS
            }
            per_source_words.append(words)

        counts = Counter(w for words in per_source_words for w in words)
        similarities = [w for w, n in counts.most_common(8) if n >= 2]

        differences: list[str] = []
        for source, words in zip(sources, per_source_words, strict=True):
            unique = sorted(w for w in words if counts[w] == 1)[:3]
            if unique:
                differences.append(f"{source.domain}: mentions {', '.join(unique)} uniquely")

        return {}, similarities, differences


class WebResearchAgent:
    def __init__(
        self,
        manager: BrowserManager,
        *,
        ranker: SourceRanker | None = None,
        extractor: ContentExtractor | None = None,
        comparison: ComparisonEngine | None = None,
    ) -> None:
        self._manager = manager
        self._ranker = ranker or SourceRanker()
        self._extractor = extractor or ContentExtractor()
        self._comparison = comparison or ComparisonEngine()

    async def run(
        self,
        *,
        goal: str,
        max_sites: int,
        max_tabs: int,
        max_steps: int,
        max_time_seconds: float,
    ) -> ResearchResult:
        started = time.monotonic()
        steps = 0

        def _budget_ok() -> bool:
            return steps < max_steps and (time.monotonic() - started) < max_time_seconds

        session = await self._manager.launch(headless=True)
        try:
            from urllib.parse import quote_plus

            search_url = f"https://www.google.com/search?q={quote_plus(goal)}"
            assert session.active_tab_id is not None  # guaranteed by launch()
            search_tab_id = session.active_tab_id
            _, nav_result = await self._manager.navigate(
                session.session_id, search_tab_id, search_url
            )
            steps += 1
            links = await session.adapter.list_links(session.tabs[search_tab_id].tab_ref)
            ranked = self._ranker.rank(
                links,
                exclude_domain=domain_of(nav_result.final_url),
                query=goal,
                max_results=min(max_sites, max_tabs),
            )

            sources: list[ResearchSource] = []
            for url in ranked:
                if not _budget_ok():
                    break
                try:
                    tab = await self._manager.new_tab(session.session_id, url=url)
                    steps += 1
                    title = await session.adapter.get_title(tab.tab_ref)
                    content = await self._extractor.extract(session.adapter, tab.tab_ref)
                    steps += 1
                    domain = domain_of(url)
                    sources.append(
                        ResearchSource(
                            url=url,
                            domain=domain,
                            title=title,
                            retrieved_content=content,
                            retrieved_at=datetime.now(UTC).isoformat(),
                            quality=_quality_of(domain),
                        )
                    )
                except Exception:
                    continue

            if not sources:
                raise ResearchBudgetExceeded(
                    f"Could not retrieve any usable source for '{goal}' within the given budget."
                )

            normalized_fields, similarities, differences = self._comparison.compare(sources)
            domains = ", ".join(s.domain for s in sources)
            summary = f"Found {len(sources)} source(s) for '{goal}': {domains}." + (
                f" Common themes: {', '.join(similarities)}." if similarities else ""
            )
            return ResearchResult(
                goal=goal,
                sources=sources,
                normalized_fields=normalized_fields,
                differences=differences,
                similarities=similarities,
                summary=summary,
            )
        finally:
            await self._manager.close(session.session_id)
