"""BrowserVerifier / BrowserWorkflowEngine. docs/phase-8/BROWSER-WORKFLOW.md."""

from __future__ import annotations

from app.services.browser.manager import BrowserManager
from app.services.browser.testing import FakeBrowserAdapter, FakePage
from app.services.browser.workflow import BrowserVerifier, BrowserWorkflowEngine


def test_verifier_detects_url_change():
    result = BrowserVerifier().verify(
        before_url="https://x/a", after_url="https://x/b", before_title="A", after_title="A"
    )
    assert result.state_changed


def test_verifier_detects_no_change():
    result = BrowserVerifier().verify(
        before_url="https://x/a", after_url="https://x/a", before_title="A", after_title="A"
    )
    assert not result.state_changed


def test_verifier_detects_title_only_change():
    result = BrowserVerifier().verify(
        before_url="https://x/a",
        after_url="https://x/a",
        before_title="Loading",
        after_title="Done",
    )
    assert result.state_changed


async def test_workflow_engine_captures_real_navigation_change():
    manager = BrowserManager(FakeBrowserAdapter)
    session = await manager.launch()
    adapter: FakeBrowserAdapter = session.adapter  # type: ignore[assignment]
    adapter.add_page("https://x/next", FakePage(title="Next Page"))
    tab = session.tabs[session.active_tab_id]
    engine = BrowserWorkflowEngine()

    async def _navigate():
        await adapter.navigate(tab.tab_ref, "https://x/next")

    _, verification = await engine.execute_and_verify(session, tab, _navigate)
    assert verification.state_changed
    assert verification.after_url == "https://x/next"


async def test_workflow_engine_reports_no_change_for_a_noop_action():
    manager = BrowserManager(FakeBrowserAdapter)
    session = await manager.launch()
    tab = session.tabs[session.active_tab_id]
    engine = BrowserWorkflowEngine()

    async def _noop():
        return None

    _, verification = await engine.execute_and_verify(session, tab, _noop)
    assert not verification.state_changed
