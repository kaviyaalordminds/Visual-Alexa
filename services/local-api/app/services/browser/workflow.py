"""BrowserWorkflowEngine / BrowserVerifier. docs/phase-8/BROWSER-WORKFLOW.md.

brief §81-84: "closed-loop control... PLAN -> ACT -> OBSERVE -> VERIFY ->
REPLAN... After every important action verify result." The PLAN/REPLAN
half of this loop is Phase 4's `AgentOrchestrator`/`RecoveryManager`,
reused unchanged (brief §86 "Use Phase 4 RecoveryManager" — see the new
browser `ErrorCategory` members classified into its existing
`_REGROUND_CATEGORIES`/`_REOBSERVE_CATEGORIES`/`_PERMANENT_CATEGORIES`
sets in `app/services/agent/recovery.py`, and into
`veyra_contracts.errors.RETRYABLE_CATEGORIES`, rather than a second
recovery engine). This module owns the ACT -> OBSERVE -> VERIFY half for
one browser action: capture state before, run the action, capture state
after, and report whether anything actually changed — real signal
`tools.py`'s click/navigate executors attach to their result rather than
assuming success.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.services.browser.manager import BrowserSession, BrowserTab

T = TypeVar("T")


@dataclass(frozen=True)
class BrowserVerification:
    state_changed: bool
    before_url: str
    after_url: str
    before_title: str
    after_title: str


class BrowserVerifier:
    """Pure comparison — no I/O — so it's trivially unit-testable on its
    own, separate from `BrowserWorkflowEngine`'s I/O-bound capture."""

    def verify(
        self, *, before_url: str, after_url: str, before_title: str, after_title: str
    ) -> BrowserVerification:
        changed = before_url != after_url or before_title != after_title
        return BrowserVerification(
            state_changed=changed,
            before_url=before_url,
            after_url=after_url,
            before_title=before_title,
            after_title=after_title,
        )


class BrowserWorkflowEngine:
    """brief §81 — the ACT -> OBSERVE -> VERIFY portion of the loop for
    one action. Real audit/timeline data (brief §142) already comes for
    free from the existing `AuditLog` row every tool call writes
    (`app/services/tool_execution.py`) — this class never duplicates
    that, it only adds the before/after comparison a raw `AuditLog` row
    doesn't carry."""

    def __init__(self, verifier: BrowserVerifier | None = None) -> None:
        self._verifier = verifier or BrowserVerifier()

    async def execute_and_verify(
        self,
        session: BrowserSession,
        tab: BrowserTab,
        action: Callable[[], Awaitable[T]],
    ) -> tuple[T, BrowserVerification]:
        before_url = await session.adapter.get_url(tab.tab_ref)
        before_title = await session.adapter.get_title(tab.tab_ref)
        result = await action()
        after_url = await session.adapter.get_url(tab.tab_ref)
        after_title = await session.adapter.get_title(tab.tab_ref)
        verification = self._verifier.verify(
            before_url=before_url,
            after_url=after_url,
            before_title=before_title,
            after_title=after_title,
        )
        return result, verification
