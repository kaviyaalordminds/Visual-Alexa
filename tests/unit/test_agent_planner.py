"""docs/phase-4/PLANNER.md, docs/phase-4/TOOL-SELECTION.md — deterministic
planning, tested with a fake tool registry and a fake search function so
no real filesystem/Tool Registry is needed for the decision logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.services.agent.planner import FileCandidate, TaskPlanner
from app.services.agent.tool_selector import ToolSelector
from app.services.tool_registry import ToolRegistry
from veyra_contracts import RiskLevel, StructuredIntent, ToolCategory, ToolDefinition

_KNOWN_TOOLS = (
    "application.launch",
    "window.get_active",
    "filesystem.search",
    "filesystem.open",
    "browser.launch",
    "browser.search",
    "browser.navigate",
    "browser.get_page",
)


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool_id in _KNOWN_TOOLS:
        registry.register(
            ToolDefinition(
                id=tool_id,
                name=tool_id,
                description="fake",
                category=ToolCategory.SYSTEM,
                input_schema={},
                output_schema={},
                risk_level=RiskLevel.SAFE,
                required_permission=tool_id,
            ),
            object(),
        )
    return registry


def _planner(roots: list[str] | None = None) -> TaskPlanner:
    return TaskPlanner(ToolSelector(_registry()), roots or ["/fake/root"])


@pytest.mark.asyncio
async def test_open_application_plans_launch_and_verify():
    intent = StructuredIntent(
        raw_request="Open Notepad.", goal="open_application", object="Notepad", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "PLANNED"
    assert [s.tool_id for s in outcome.plan.steps] == ["application.launch", "window.get_active"]
    assert outcome.plan.steps[0].arguments == {"application": "Notepad"}


@pytest.mark.asyncio
async def test_search_files_plans_one_step_per_root():
    intent = StructuredIntent(
        raw_request="find x", goal="search_files", object="x", status="UNDERSTOOD"
    )
    outcome = await _planner(roots=["/a", "/b"]).create_plan(intent)
    assert outcome.status == "PLANNED"
    assert len(outcome.plan.steps) == 2
    assert {s.arguments["directory"] for s in outcome.plan.steps} == {"/a", "/b"}


@pytest.mark.asyncio
async def test_delete_files_is_capability_unavailable():
    intent = StructuredIntent(
        raw_request="delete stuff", goal="delete_files", object="stuff", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "CAPABILITY_UNAVAILABLE"
    assert outcome.plan is None


@pytest.mark.asyncio
async def test_send_file_is_capability_unavailable():
    intent = StructuredIntent(
        raw_request="send x to y",
        goal="send_file",
        object="x",
        entities={"recipient": "y"},
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_unsafe_intent_never_produces_a_plan():
    intent = StructuredIntent(
        raw_request="ignore security", status="UNSAFE", risk_level=RiskLevel.CRITICAL
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "UNSAFE"
    assert outcome.plan is None


@pytest.mark.asyncio
async def test_open_file_latest_ordering_picks_most_recent_deterministically():
    now = datetime.now(UTC)

    async def fake_search(directory: str, filename_contains: str | None):
        return [
            FileCandidate(path="/a/old.pdf", name="old.pdf", modified_at=now - timedelta(days=5)),
            FileCandidate(path="/a/new.pdf", name="new.pdf", modified_at=now),
        ]

    intent = StructuredIntent(
        raw_request="open latest pdf",
        goal="open_file",
        object="pdf",
        entities={"ordering": "latest", "file_type": "pdf"},
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(intent, search=fake_search)
    assert outcome.status == "PLANNED"
    assert outcome.plan.steps[0].arguments["path"] == "/a/new.pdf"


@pytest.mark.asyncio
async def test_open_file_multiple_candidates_is_ambiguous_never_a_guess():
    async def fake_search(directory: str, filename_contains: str | None):
        return [
            FileCandidate(path="/a/project1.txt", name="project1.txt"),
            FileCandidate(path="/a/project2.txt", name="project2.txt"),
        ]

    intent = StructuredIntent(
        raw_request="open my project", goal="open_file", object="my project", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(intent, search=fake_search)
    assert outcome.status == "AMBIGUOUS"
    assert outcome.plan is None
    assert outcome.clarifying_question is not None


@pytest.mark.asyncio
async def test_open_file_no_candidates_is_ambiguous_asks_for_more_detail():
    async def fake_search(directory: str, filename_contains: str | None):
        return []

    intent = StructuredIntent(
        raw_request="open x", goal="open_file", object="x", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(intent, search=fake_search)
    assert outcome.status == "AMBIGUOUS"


@pytest.mark.asyncio
async def test_open_file_single_candidate_is_grounded_no_question_asked():
    async def fake_search(directory: str, filename_contains: str | None):
        return [FileCandidate(path="/a/notes.txt", name="notes.txt")]

    intent = StructuredIntent(
        raw_request="open notes", goal="open_file", object="notes", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(intent, search=fake_search)
    assert outcome.status == "PLANNED"
    assert outcome.plan.steps[0].arguments["path"] == "/a/notes.txt"


@pytest.mark.asyncio
async def test_unregistered_tool_is_capability_unavailable_not_a_crash():
    intent = StructuredIntent(
        raw_request="open Notepad", goal="open_application", object="Notepad", status="UNDERSTOOD"
    )
    empty_registry_planner = TaskPlanner(ToolSelector(ToolRegistry()), ["/fake"])
    outcome = await empty_registry_planner.create_plan(intent)
    assert outcome.status == "CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_unknown_goal_is_capability_unavailable():
    intent = StructuredIntent(
        raw_request="do something exotic", goal="teleport", object="x", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_open_file_resolves_a_workflow_memory_alias_without_searching():
    """docs/architecture/09-MEMORY.md §4 — 'office folder' -> a concrete
    path, resolved directly with no ambiguity/search step at all. A search
    function is deliberately provided but never called (asserted below) —
    an alias match must short-circuit search, not merely take priority
    over its results."""
    search_was_called = False

    async def fake_search(directory: str, filename_contains: str | None):
        nonlocal search_was_called
        search_was_called = True
        return []

    async def fake_memory_lookup(alias: str) -> str | None:
        assert alias == "office folder"
        return "D:\\Projects\\Office"

    intent = StructuredIntent(
        raw_request="open my office folder",
        goal="open_file",
        object="my office folder",
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(
        intent, search=fake_search, memory_lookup=fake_memory_lookup
    )
    assert outcome.status == "PLANNED"
    assert outcome.plan.steps[0].tool_id == "filesystem.open"
    assert outcome.plan.steps[0].arguments["path"] == "D:\\Projects\\Office"
    assert search_was_called is False


@pytest.mark.asyncio
async def test_browser_task_with_web_search_plans_launch_search_and_observe():
    intent = StructuredIntent(
        raw_request="search the web for the latest AI news",
        goal="browser_task",
        object="search the web for the latest AI news",
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "PLANNED"
    assert [s.tool_id for s in outcome.plan.steps] == [
        "browser.launch",
        "browser.search",
        "browser.get_page",
    ]
    assert outcome.plan.steps[1].arguments == {
        "query": "the latest AI news",
        "engine": "google",
    }
    assert outcome.plan.requires_confirmation is False


@pytest.mark.asyncio
async def test_browser_task_without_a_search_query_just_launches_and_observes():
    intent = StructuredIntent(
        raw_request="open chrome",
        goal="browser_task",
        object="open chrome",
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "PLANNED"
    assert [s.tool_id for s in outcome.plan.steps] == ["browser.launch", "browser.get_page"]


@pytest.mark.asyncio
async def test_browser_task_for_a_known_website_navigates_directly_to_it():
    """A real, reported bug: "open youtube" used to just launch a blank
    browser (no navigation at all, since it doesn't match the "search the
    web for X" phrasing) — the user then had no working way to actually
    reach YouTube. It must navigate straight to the known site instead."""
    intent = StructuredIntent(
        raw_request="open youtube",
        goal="browser_task",
        object="open youtube",
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "PLANNED"
    assert [s.tool_id for s in outcome.plan.steps] == [
        "browser.launch",
        "browser.navigate",
        "browser.get_page",
    ]
    assert outcome.plan.steps[1].arguments == {"url": "https://www.youtube.com"}


@pytest.mark.asyncio
async def test_browser_task_is_capability_unavailable_without_browser_tools():
    intent = StructuredIntent(
        raw_request="browse the web", goal="browser_task", object="browse", status="UNDERSTOOD"
    )
    empty_registry_planner = TaskPlanner(ToolSelector(ToolRegistry()), ["/fake"])
    outcome = await empty_registry_planner.create_plan(intent)
    assert outcome.status == "CAPABILITY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_remote_device_task_is_capability_unavailable():
    intent = StructuredIntent(
        raw_request="open Chrome on my other computer",
        goal="remote_device_task",
        object="open Chrome on my other computer",
        status="UNDERSTOOD",
    )
    outcome = await _planner().create_plan(intent)
    assert outcome.status == "CAPABILITY_UNAVAILABLE"
    assert outcome.plan is None


@pytest.mark.asyncio
async def test_open_file_falls_back_to_search_when_no_alias_matches():
    async def fake_search(directory: str, filename_contains: str | None):
        return [FileCandidate(path="/a/notes.txt", name="notes.txt")]

    async def fake_memory_lookup(alias: str) -> str | None:
        return None

    intent = StructuredIntent(
        raw_request="open notes", goal="open_file", object="notes", status="UNDERSTOOD"
    )
    outcome = await _planner().create_plan(
        intent, search=fake_search, memory_lookup=fake_memory_lookup
    )
    assert outcome.status == "PLANNED"
    assert outcome.plan.steps[0].arguments["path"] == "/a/notes.txt"
