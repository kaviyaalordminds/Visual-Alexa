"""docs/phase-7/TOOL-DISCOVERY.md — search_tools narrows a catalog by
keyword/category without needing an LLM planner to exist yet."""

from __future__ import annotations

import time

from veyra_contracts import RiskLevel, ToolCategory, ToolDefinition, search_tools


def _tool(id: str, category: ToolCategory, keywords: list[str] | None = None) -> ToolDefinition:
    return ToolDefinition(
        id=id,
        name=id,
        description=f"Does {id}.",
        category=category,
        input_schema={},
        output_schema={},
        risk_level=RiskLevel.SAFE,
        required_permission="test.permission",
        keywords=keywords or [],
    )


_CATALOG = [
    _tool("filesystem.search", ToolCategory.FILESYSTEM, keywords=["find", "locate"]),
    _tool("communication.send_email", ToolCategory.COMMUNICATION, keywords=["mail", "message"]),
    _tool("media.play", ToolCategory.MEDIA, keywords=["music", "song"]),
]


def test_no_filters_returns_everything():
    assert search_tools(_CATALOG) == _CATALOG


def test_category_filter():
    result = search_tools(_CATALOG, category=ToolCategory.MEDIA)
    assert [t.id for t in result] == ["media.play"]


def test_query_matches_id():
    result = search_tools(_CATALOG, query="filesystem")
    assert [t.id for t in result] == ["filesystem.search"]


def test_query_matches_keyword_not_id_or_name():
    result = search_tools(_CATALOG, query="song")
    assert [t.id for t in result] == ["media.play"]


def test_query_matches_description():
    result = search_tools(_CATALOG, query="does communication.send_email")
    assert [t.id for t in result] == ["communication.send_email"]


def test_query_is_case_insensitive():
    result = search_tools(_CATALOG, query="MAIL")
    assert [t.id for t in result] == ["communication.send_email"]


def test_query_and_category_combine():
    result = search_tools(_CATALOG, query="find", category=ToolCategory.MEDIA)
    assert result == []


def test_empty_query_string_is_ignored():
    assert search_tools(_CATALOG, query="   ") == _CATALOG


def test_no_match_returns_empty():
    assert search_tools(_CATALOG, query="nonexistent-xyz") == []


def test_scales_to_hundreds_of_tools_quickly():
    """brief §158 — the planner must not receive every tool description
    on every request; the search itself must also stay fast at the scale
    a real, larger deployment could reach."""
    catalog = [
        _tool(f"category{i % 12}.tool{i}", ToolCategory.CUSTOM, keywords=[f"kw{i}"])
        for i in range(500)
    ]
    started = time.monotonic()
    result = search_tools(catalog, query="kw250")
    elapsed = time.monotonic() - started
    assert [t.id for t in result] == [f"category{250 % 12}.tool250"]
    assert elapsed < 0.1
