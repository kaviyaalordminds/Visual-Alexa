"""BrowserManager / BrowserRegistry / tab & session resolution.
docs/phase-8/BROWSER-SESSION.md, docs/phase-8/TAB-MANAGEMENT.md."""

from __future__ import annotations

import pytest
from app.services.browser.manager import (
    BrowserManager,
    BrowserManagerError,
    UnknownSessionError,
    UnknownTabError,
)
from app.services.browser.testing import FakeBrowserAdapter, FakePage


def _manager(**kwargs) -> BrowserManager:
    return BrowserManager(FakeBrowserAdapter, **kwargs)


async def test_launch_creates_session_with_one_active_tab():
    m = _manager()
    session = await m.launch()
    assert m.active_session_id == session.session_id
    assert len(session.tabs) == 1
    assert session.active_tab_id is not None


async def test_require_session_without_launch_raises():
    m = _manager()
    with pytest.raises(UnknownSessionError):
        m.require_session(None)


async def test_new_tab_and_switch_tab():
    m = _manager()
    session = await m.launch()
    first_tab_id = session.active_tab_id
    tab = await m.new_tab(session.session_id, url="https://x/")
    assert tab.tab_id != first_tab_id
    assert session.active_tab_id == tab.tab_id
    switched = m.switch_tab(session.session_id, first_tab_id)
    assert switched.tab_id == first_tab_id
    assert session.active_tab_id == first_tab_id


async def test_close_tab_falls_back_to_remaining_tab():
    m = _manager()
    session = await m.launch()
    first_tab_id = session.active_tab_id
    second = await m.new_tab(session.session_id)
    await m.close_tab(session.session_id, second.tab_id)
    assert session.active_tab_id == first_tab_id
    assert second.tab_id not in session.tabs


async def test_resolve_tab_target_defaults_to_active():
    m = _manager()
    session = await m.launch()
    resolved_session, resolved_tab = m.resolve_tab_target(None)
    assert resolved_session.session_id == session.session_id
    assert resolved_tab.tab_id == session.active_tab_id


async def test_resolve_tab_target_finds_owning_session_not_just_active():
    m = _manager()
    first = await m.launch()
    second = await m.launch()
    assert m.active_session_id == second.session_id
    # a tab in the first (now non-active) session must still resolve correctly.
    resolved_session, resolved_tab = m.resolve_tab_target(first.active_tab_id)
    assert resolved_session.session_id == first.session_id
    assert resolved_tab.tab_id == first.active_tab_id


async def test_resolve_tab_target_unknown_tab_raises():
    m = _manager()
    await m.launch()
    with pytest.raises(UnknownTabError):
        m.resolve_tab_target("does-not-exist")


async def test_find_tab_matches_title_url_or_domain():
    m = _manager()
    session = await m.launch()
    adapter: FakeBrowserAdapter = session.adapter  # type: ignore[assignment]
    adapter.add_page("https://python.org/tutorial", FakePage(title="Python Tutorial"))
    await m.new_tab(session.session_id, url="https://python.org/tutorial")
    found = m.find_tab(session.session_id, "python tutorial")
    assert found is not None
    assert found.url == "https://python.org/tutorial"


async def test_find_tab_no_match_returns_none():
    m = _manager()
    session = await m.launch()
    assert m.find_tab(session.session_id, "nonexistent content") is None


async def test_max_sessions_enforced():
    m = _manager(max_sessions=1)
    await m.launch()
    with pytest.raises(BrowserManagerError):
        await m.launch()


async def test_max_tabs_per_session_enforced():
    m = _manager(max_tabs_per_session=1)
    session = await m.launch()
    with pytest.raises(BrowserManagerError):
        await m.new_tab(session.session_id)


async def test_focus_switches_active_session():
    m = _manager()
    first = await m.launch()
    await m.launch()
    m.focus(first.session_id)
    assert m.active_session_id == first.session_id


async def test_navigate_updates_tab_url_and_title():
    m = _manager()
    session = await m.launch()
    adapter: FakeBrowserAdapter = session.adapter  # type: ignore[assignment]
    adapter.add_page("https://x/page", FakePage(title="Page Title"))
    tab, result = await m.navigate(session.session_id, session.active_tab_id, "https://x/page")
    assert result.ok
    assert tab.url == "https://x/page"
    assert tab.title == "Page Title"


async def test_close_removes_session_and_reassigns_active():
    m = _manager()
    first = await m.launch()
    second = await m.launch()
    await m.close(second.session_id)
    assert m.active_session_id == first.session_id
    assert m.registry.get(second.session_id) is None


async def test_close_all_clears_every_session():
    m = _manager()
    await m.launch()
    await m.launch()
    await m.close_all()
    assert m.registry.list() == []
    assert m.active_session_id is None


async def test_new_window_detection_registers_popup_as_new_tab():
    m = _manager()
    session = await m.launch()
    adapter: FakeBrowserAdapter = session.adapter  # type: ignore[assignment]
    before = len(session.tabs)
    adapter.add_page("https://popup/", FakePage(title="Popup"))
    await adapter.simulate_popup(session.tabs[session.active_tab_id].tab_ref, url="https://popup/")
    assert len(session.tabs) == before + 1
    popup_tabs = [t for t in session.tabs.values() if t.is_popup]
    assert len(popup_tabs) == 1
