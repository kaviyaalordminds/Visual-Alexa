"""TaskPlanner — StructuredIntent -> ExecutionPlan. docs/phase-4/PLANNER.md.

Deterministic: a small, explicit set of goal templates
(docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §8), not a general-purpose
planner. A goal with no matching template, or one whose action has no
registered tool at all (send a message, control an IoT device, browse the
web), returns CAPABILITY_UNAVAILABLE honestly rather than fabricating a
plan. Never guesses between ambiguous candidates — always defers to
`veyra_contracts.resolve_ambiguity`.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from veyra_contracts import (
    AmbiguityCandidate,
    ExecutionPlan,
    PlanStep,
    RiskLevel,
    StructuredIntent,
    resolve_ambiguity,
)

from app.services.agent.tool_selector import ToolSelector, UnknownToolSelectedError

PlanStatus = Literal["PLANNED", "AMBIGUOUS", "CAPABILITY_UNAVAILABLE", "UNSAFE", "INVALID"]


@dataclass
class FileCandidate:
    path: str
    name: str
    modified_at: datetime | None = None
    size_bytes: int | None = None


SearchFn = Callable[[str, str | None], Awaitable[list[FileCandidate]]]
"""`(directory, filename_contains) -> candidates` — injected so
`TaskPlanner`'s decision logic stays unit-testable without a real
filesystem or Tool Registry. The orchestrator supplies a real
implementation that calls `filesystem.search` through the normal
Policy-Engine-gated path; unit tests supply a fake returning canned
candidates."""

MemoryLookupFn = Callable[[str], Awaitable[str | None]]
"""`(alias) -> resolved_path` (or `None` if no matching alias exists).
docs/architecture/09-MEMORY.md §4 — `WorkflowMemory` alias resolution
("office folder" -> `D:\\Projects\\Office`): injected the same way as
`SearchFn` so the planner stays unit-testable without a real Memory table;
the orchestrator supplies a real implementation backed by `/memory`'s own
`Memory` rows (category=WORKFLOW), never a second, parallel alias store."""


@dataclass
class PlanOutcome:
    status: PlanStatus
    plan: ExecutionPlan | None = None
    clarifying_question: str | None = None
    reason: str | None = None
    candidates: list[AmbiguityCandidate] = field(default_factory=list)


# Goals with no registered tool anywhere in Phase 1-3 — brief §69/§70/§59:
# "return CAPABILITY_UNAVAILABLE... do not pretend."
_UNAVAILABLE_GOALS: dict[str, str] = {
    "send_file": "Sending files (email/chat/WhatsApp) is not available yet.",
    "control_device": "Smart-device control is not available yet.",
    "delete_files": "Deleting files is not available yet — Phase 2 deliberately "
    "has no delete tool (docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §7).",
    # docs/security/04-DEVICE-TRUST.md — VEYRA only ever controls this PC.
    # Never silently substitute a local action for a request that named
    # another machine/device.
    "remote_device_task": "Controlling another computer or device is not "
    "available — VEYRA only controls this PC.",
}

# Phase 11 — "browser_task" now has a real, bounded planning template
# (`_plan_browser_task` below) built on Phase 8's already-real Playwright
# browser tools, so it's no longer in `_UNAVAILABLE_GOALS`. Deliberately
# narrow: it plans launching a browser and, when the request names a web
# search, running that search through `browser.search`'s own supported
# engines — never a multi-site, click-by-guess sequence (e.g. "find and
# play the first video"), which would mean fabricating a target this
# deterministic planner never actually observed. That stays a real,
# already-existing capability the orchestrator can still use step by step
# (docs/phase-8/BROWSER-TOOLS.md) — just not something this template
# preplans blindly.
_WEB_SEARCH_QUERY_RE = re.compile(r"search\s+(?:the\s+)?web\s+(?:for\s+)?(.+)", re.IGNORECASE)


class TaskPlanner:
    def __init__(self, tool_selector: ToolSelector, search_roots: list[str]) -> None:
        self._tools = tool_selector
        self._search_roots = search_roots or []

    async def create_plan(
        self,
        intent: StructuredIntent,
        *,
        search: SearchFn | None = None,
        memory_lookup: MemoryLookupFn | None = None,
    ) -> PlanOutcome:
        if intent.status == "UNSAFE":
            return PlanOutcome(status="UNSAFE", reason="Request matched a disallowed pattern.")
        if intent.status != "UNDERSTOOD" or not intent.goal:
            return PlanOutcome(status="INVALID", reason="Intent was not understood.")

        if intent.goal == "delete_files":
            preview = ""
            if search is not None:
                candidates = await self._search_all_roots(search, intent)
                if candidates:
                    total = sum(c.size_bytes or 0 for c in candidates)
                    preview = (
                        f" (found {len(candidates)} matching file(s), "
                        f"~{total} bytes, that would have been affected)"
                    )
            return PlanOutcome(
                status="CAPABILITY_UNAVAILABLE",
                reason=_UNAVAILABLE_GOALS["delete_files"] + preview,
            )

        if intent.goal in _UNAVAILABLE_GOALS:
            return PlanOutcome(
                status="CAPABILITY_UNAVAILABLE", reason=_UNAVAILABLE_GOALS[intent.goal]
            )

        if intent.goal == "open_application":
            return self._plan_open_application(intent)

        if intent.goal == "search_files":
            return self._plan_search_files(intent)

        if intent.goal == "open_file":
            return await self._plan_open_file(intent, search, memory_lookup)

        if intent.goal == "browser_task":
            return self._plan_browser_task(intent)

        if intent.goal == "create_folder":
            return self._plan_create_folder(intent)

        return PlanOutcome(
            status="CAPABILITY_UNAVAILABLE",
            reason=f"No planning template exists for goal '{intent.goal}'.",
        )

    def _plan_open_application(self, intent: StructuredIntent) -> PlanOutcome:
        try:
            self._tools.select("application.launch")
            self._tools.select("window.get_active")
        except UnknownToolSelectedError as exc:
            return PlanOutcome(status="CAPABILITY_UNAVAILABLE", reason=str(exc))
        steps = [
            PlanStep(
                sequence=1,
                description=f"Launch '{intent.object}'.",
                intent=intent.goal,
                tool_id="application.launch",
                arguments={"application": intent.object},
                expected_outcome="The application process is running.",
                risk_level=RiskLevel.SAFE,
                verification_strategy="process_and_window_detection",
            ),
            PlanStep(
                sequence=2,
                description="Verify the application's window is active.",
                intent="verify",
                tool_id="window.get_active",
                arguments={},
                expected_outcome="A window belonging to the launched application is active.",
                risk_level=RiskLevel.SAFE,
                verification_strategy="window_state_check",
            ),
        ]
        return PlanOutcome(status="PLANNED", plan=self._build_plan(intent.goal, steps))

    def _plan_browser_task(self, intent: StructuredIntent) -> PlanOutcome:
        try:
            self._tools.select("browser.launch")
            self._tools.select("browser.get_page")
        except UnknownToolSelectedError as exc:
            return PlanOutcome(status="CAPABILITY_UNAVAILABLE", reason=str(exc))

        steps = [
            PlanStep(
                sequence=1,
                description="Launch a browser.",
                intent=intent.goal,
                tool_id="browser.launch",
                # Visible, not headless — the user asked VEYRA to open a
                # browser, so they expect to see the window it opens.
                arguments={"headless": False},
                expected_outcome="A browser session is open.",
                risk_level=RiskLevel.SAFE,
            )
        ]

        query_match = _WEB_SEARCH_QUERY_RE.search(intent.object or "")
        if query_match:
            try:
                self._tools.select("browser.search")
            except UnknownToolSelectedError as exc:
                return PlanOutcome(status="CAPABILITY_UNAVAILABLE", reason=str(exc))
            query = query_match.group(1).strip().rstrip(".")
            steps.append(
                PlanStep(
                    sequence=2,
                    description=f"Search the web for '{query}'.",
                    intent=intent.goal,
                    tool_id="browser.search",
                    arguments={"query": query, "engine": "google"},
                    expected_outcome="Search results are loaded.",
                    risk_level=RiskLevel.SAFE,
                )
            )

        steps.append(
            PlanStep(
                sequence=len(steps) + 1,
                description="Observe the loaded page to confirm it's ready.",
                intent="verify",
                tool_id="browser.get_page",
                arguments={},
                expected_outcome="A semantic observation of the current page is returned.",
                risk_level=RiskLevel.SAFE,
                verification_strategy="page_observation",
            )
        )
        return PlanOutcome(status="PLANNED", plan=self._build_plan(intent.goal, steps))

    def _plan_search_files(self, intent: StructuredIntent) -> PlanOutcome:
        try:
            self._tools.select("filesystem.search")
        except UnknownToolSelectedError as exc:
            return PlanOutcome(status="CAPABILITY_UNAVAILABLE", reason=str(exc))
        steps = [
            PlanStep(
                sequence=i + 1,
                description=f"Search '{root}' for '{intent.object}'.",
                intent=intent.goal,
                tool_id="filesystem.search",
                arguments=self._search_criteria(root, intent),
                expected_outcome="Matching files are returned.",
                risk_level=RiskLevel.SAFE,
            )
            for i, root in enumerate(self._search_roots)
        ]
        if not steps:
            return PlanOutcome(
                status="CAPABILITY_UNAVAILABLE", reason="No searchable location is configured."
            )
        return PlanOutcome(status="PLANNED", plan=self._build_plan(intent.goal, steps))

    def _plan_create_folder(self, intent: StructuredIntent) -> PlanOutcome:
        try:
            self._tools.select("filesystem.create_folder")
        except UnknownToolSelectedError as exc:
            return PlanOutcome(status="CAPABILITY_UNAVAILABLE", reason=str(exc))
        if not self._search_roots:
            return PlanOutcome(
                status="CAPABILITY_UNAVAILABLE", reason="No writable location is configured."
            )
        # Same sandboxed-roots concept `_plan_search_files` already uses
        # (docs/phase-2/FILESYSTEM-CONTROL.md) — the first configured
        # allowed root is the default location when the request doesn't
        # name one. A location-aware default ("in Downloads") is real
        # future work, not attempted here.
        parent = self._search_roots[0]
        name = (intent.object or "").strip()
        steps = [
            PlanStep(
                sequence=1,
                description=f"Create folder '{name}' in '{parent}'.",
                intent=intent.goal,
                tool_id="filesystem.create_folder",
                arguments={"parent": parent, "name": name},
                expected_outcome="The folder exists on disk.",
                risk_level=RiskLevel.MODERATE,
                verification_strategy="filesystem_state_detection",
            )
        ]
        return PlanOutcome(status="PLANNED", plan=self._build_plan(intent.goal, steps))

    async def _plan_open_file(
        self,
        intent: StructuredIntent,
        search: SearchFn | None,
        memory_lookup: MemoryLookupFn | None = None,
    ) -> PlanOutcome:
        try:
            self._tools.select("filesystem.open")
        except UnknownToolSelectedError as exc:
            return PlanOutcome(status="CAPABILITY_UNAVAILABLE", reason=str(exc))

        # docs/architecture/09-MEMORY.md §4 — a user-defined WorkflowMemory
        # alias ("office folder" -> a concrete path) is checked first and,
        # if found, resolves the target directly: no ambiguity to ask
        # about, no filesystem search needed, because the user already told
        # VEYRA exactly what they meant. Falls through to the ordinary
        # search-based resolution below when no alias matches, never a hard
        # failure — an alias is an optional shortcut, not a requirement.
        if memory_lookup is not None:
            alias = self._alias_query(intent)
            if alias:
                resolved_path = await memory_lookup(alias)
                if resolved_path:
                    return self._plan_single_file_open(intent, resolved_path)

        if search is None:
            return PlanOutcome(
                status="CAPABILITY_UNAVAILABLE",
                reason="No filesystem search capability is available to locate the file.",
            )

        candidates = await self._search_all_roots(search, intent)
        if not candidates:
            return PlanOutcome(
                status="AMBIGUOUS",
                clarifying_question=(
                    f"I couldn't find anything matching '{intent.object}'. "
                    "Could you give me more detail?"
                ),
            )

        if intent.entities.get("ordering") == "latest":
            best = max(candidates, key=lambda c: c.modified_at or datetime.min.replace(tzinfo=UTC))
            return self._plan_single_file_open(intent, best.path)

        ambiguity_candidates = [
            AmbiguityCandidate(id=c.path, label=c.name) for c in candidates
        ]
        resolution = resolve_ambiguity(ambiguity_candidates, target_description=intent.object or "")
        if not resolution.resolved:
            return PlanOutcome(
                status="AMBIGUOUS",
                clarifying_question=resolution.clarifying_question,
                candidates=ambiguity_candidates,
            )
        return self._plan_single_file_open(intent, resolution.candidate.id)  # type: ignore[union-attr]

    def _plan_single_file_open(self, intent: StructuredIntent, path: str) -> PlanOutcome:
        steps = [
            PlanStep(
                sequence=1,
                description=f"Open '{path}'.",
                intent=intent.goal,
                tool_id="filesystem.open",
                arguments={"path": path},
                expected_outcome="The file is opened in its associated application.",
                risk_level=RiskLevel.SAFE,
            )
        ]
        return PlanOutcome(status="PLANNED", plan=self._build_plan(intent.goal, steps))

    async def _search_all_roots(
        self, search: SearchFn, intent: StructuredIntent
    ) -> list[FileCandidate]:
        query = self._filename_query(intent)
        results: list[FileCandidate] = []
        for root in self._search_roots:
            results.extend(await search(root, query))
        extension = intent.entities.get("file_type")
        if extension:
            results = [c for c in results if c.name.lower().endswith(f".{extension}")]
        cutoff = self._time_cutoff(intent)
        if cutoff is not None:
            results = [c for c in results if c.modified_at is not None and c.modified_at >= cutoff]
        return results

    def _filename_query(self, intent: StructuredIntent) -> str | None:
        words = [
            w
            for w in (intent.object or "").split()
            if w.lower() not in {"my", "the", "a", "an"}
        ]
        return words[0] if words else None

    def _alias_query(self, intent: StructuredIntent) -> str:
        """Unlike `_filename_query` (which keeps only the first word — a
        filename search term), a WorkflowMemory key is the whole phrase the
        user defined ("office folder", not just "office")."""
        words = [
            w
            for w in (intent.object or "").split()
            if w.lower() not in {"my", "the", "a", "an"}
        ]
        return " ".join(words)

    def _time_cutoff(self, intent: StructuredIntent) -> datetime | None:
        constraint = intent.entities.get("time_constraint")
        now = datetime.now(UTC)
        if constraint == "yesterday":
            return (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
        if constraint == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if constraint == "last week":
            return now - timedelta(days=7)
        return None

    def _search_criteria(self, root: str, intent: StructuredIntent) -> dict:
        criteria: dict = {"directory": root}
        query = self._filename_query(intent)
        if query:
            criteria["filename_contains"] = query
        extension = intent.entities.get("file_type")
        if extension:
            criteria["extension"] = extension
        return criteria

    def _build_plan(self, goal: str, steps: list[PlanStep]) -> ExecutionPlan:
        risk = max((s.risk_level for s in steps), key=list(RiskLevel).index, default=RiskLevel.SAFE)
        return ExecutionPlan(
            goal=goal,
            steps=steps,
            risk_level=risk,
            requires_confirmation=risk in (RiskLevel.SENSITIVE, RiskLevel.CRITICAL),
        )
