"""SourceRanker / ComparisonEngine (pure logic). docs/phase-8/WEB-RESEARCH.md,
docs/phase-8/WEB-COMPARISON.md."""

from __future__ import annotations

from app.services.browser.research import ComparisonEngine, SourceRanker
from veyra_contracts import ResearchSource


def test_ranker_excludes_search_engine_domain():
    links = [
        ("Result", "https://www.google.com/search?q=x"),
        ("Real Site", "https://example.com/x"),
    ]
    ranked = SourceRanker().rank(links, exclude_domain="www.google.com", query="x", max_results=5)
    assert ranked == ["https://example.com/x"]


def test_ranker_deduplicates_by_domain():
    links = [
        ("A", "https://example.com/a"),
        ("B", "https://example.com/b"),
        ("C", "https://other.com/c"),
    ]
    ranked = SourceRanker().rank(links, exclude_domain="google.com", query="a b c", max_results=5)
    assert len(ranked) == 2


def test_ranker_unwraps_google_redirect():
    links = [("Result", "https://www.google.com/url?q=https://real-site.com/page&sa=U")]
    ranked = SourceRanker().rank(
        links, exclude_domain="www.google.com", query="page", max_results=5
    )
    assert ranked == ["https://real-site.com/page"]


def test_ranker_prefers_query_matching_anchor_text():
    links = [
        ("Unrelated", "https://a.com/1"),
        ("Laptop deals 2026", "https://b.com/2"),
    ]
    ranked = SourceRanker().rank(
        links, exclude_domain="google.com", query="laptop deals", max_results=1
    )
    assert ranked == ["https://b.com/2"]


def test_ranker_respects_max_results():
    links = [(f"Site {i}", f"https://site{i}.com/x") for i in range(10)]
    ranked = SourceRanker().rank(links, exclude_domain="google.com", query="site", max_results=3)
    assert len(ranked) == 3


def _source(domain: str, content: str) -> ResearchSource:
    return ResearchSource(
        url=f"https://{domain}/",
        domain=domain,
        title=domain,
        retrieved_content=content,
        retrieved_at="2026-01-01T00:00:00Z",
        quality="unknown",
    )


def test_comparison_engine_needs_at_least_two_sources():
    fields, sims, diffs = ComparisonEngine().compare([_source("a.com", "some content")])
    assert fields == {} and sims == [] and diffs == []


def test_comparison_engine_finds_common_words():
    sources = [
        _source("a.com", "This laptop has excellent battery life and performance."),
        _source("b.com", "The battery life on this laptop is excellent for the price."),
    ]
    _, similarities, _ = ComparisonEngine().compare(sources)
    assert "battery" in similarities
    assert "laptop" in similarities


def test_comparison_engine_finds_unique_differences():
    sources = [
        _source("a.com", "This laptop has a fingerprint sensor unique to this model."),
        _source("b.com", "This laptop has a longer warranty period than most."),
    ]
    _, _, differences = ComparisonEngine().compare(sources)
    assert any("a.com" in d for d in differences)
    assert any("b.com" in d for d in differences)
