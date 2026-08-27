"""BrowserManager / BrowserRegistry / BrowserSession / BrowserWindow /
BrowserTab / BrowserState. docs/phase-8/BROWSER-SESSION.md,
docs/phase-8/TAB-MANAGEMENT.md.

One process-wide `BrowserManager` singleton (module-level, like
`tool_registry`/`integration_registry`/`device_pairing_service` before
it) tracks every live `BrowserSession` in memory — a launched browser
process cannot outlive this process anyway (CLAUDE.md: the Local API is
the only process that can invoke a tool), so there is nothing here that
needs a second, DB-backed source of truth. Every browser *action* still
gets exactly one `AuditLog` row via the normal `execute_tool_call` path
(tools.py) — this module owns only the runtime bookkeeping, never
security decisions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

from veyra_contracts import BrowserSessionInfo, BrowserTabInfo, DomainTrustStatus

from app.services.browser.adapter import (
    AdapterError,
    BrowserAdapter,
    DownloadEvent,
    NavigationResult,
)
from app.services.browser.downloads import DownloadManager


def _now() -> datetime:
    return datetime.now(UTC)


def domain_of(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


class BrowserManagerError(RuntimeError):
    pass


class UnknownSessionError(BrowserManagerError):
    pass


class UnknownTabError(BrowserManagerError):
    pass


@dataclass
class BrowserTab:
    tab_id: str
    tab_ref: str  # adapter-internal handle
    title: str = ""
    url: str = "about:blank"
    status: str = "complete"  # 'loading' | 'complete' | 'crashed' | 'closed'
    favicon: str | None = None
    is_popup: bool = False

    @property
    def domain(self) -> str:
        return domain_of(self.url)

    def to_info(self, *, active: bool) -> BrowserTabInfo:
        return BrowserTabInfo(
            tab_id=self.tab_id,
            title=self.title,
            url=self.url,
            domain=self.domain,
            status=self.status,
            active=active,
            favicon=self.favicon,
        )


@dataclass
class BrowserWindow:
    """brief §4/§53 — a coarse grouping of tabs. Playwright's own model
    (one `BrowserContext`, many `Page`s) has no separate concept of
    distinct OS-level browser windows, so — documented honestly rather
    than faked — every tab in a session belongs to that session's single
    default window; a page the site itself opens (`window.open`,
    `target=_blank`) is still tracked as a new tab (`is_popup=True`),
    never silently dropped."""

    window_id: str
    tab_ids: list[str] = field(default_factory=list)


class BrowserState:
    """Connection lifecycle of one `BrowserSession`'s underlying
    process — a plain string-constant set, not a `veyra_contracts` enum,
    since it never crosses the service boundary (BrowserSessionInfo
    carries `connection_status` as a free string)."""

    LAUNCHING = "LAUNCHING"
    READY = "READY"
    CLOSED = "CLOSED"
    CRASHED = "CRASHED"


@dataclass
class BrowserSession:
    session_id: str
    browser_type: str
    adapter: BrowserAdapter
    window: BrowserWindow
    tabs: dict[str, BrowserTab] = field(default_factory=dict)
    active_tab_id: str | None = None
    state: str = BrowserState.LAUNCHING
    created_at: datetime = field(default_factory=_now)
    last_activity: datetime = field(default_factory=_now)

    def touch(self) -> None:
        self.last_activity = _now()

    def to_info(self) -> BrowserSessionInfo:
        return BrowserSessionInfo(
            session_id=self.session_id,
            browser_type=self.browser_type,
            connection_status=self.state,
            created_at=self.created_at.isoformat(),
            last_activity=self.last_activity.isoformat(),
            tabs=[
                tab.to_info(active=tab.tab_id == self.active_tab_id) for tab in self.tabs.values()
            ],
            active_tab_id=self.active_tab_id,
        )


class BrowserRegistry:
    """Pure bookkeeping — `BrowserManager` is the only writer."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    def add(self, session: BrowserSession) -> None:
        self._sessions[session.session_id] = session

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> BrowserSession | None:
        return self._sessions.get(session_id)

    def list(self) -> list[BrowserSession]:
        return list(self._sessions.values())


AdapterFactory = Callable[[], BrowserAdapter]


class BrowserManager:
    """The single object every `browser.*` tool executor calls into.
    docs/phase-8/BROWSER-ARCHITECTURE.md §4. Tracks one 'active' session
    (set by `launch`/`focus`) as the implicit target for a tool call that
    doesn't name one explicitly — mirrors how a real desktop user has one
    foreground browser window even while multiple profiles/sessions
    exist (brief §116 'Session Isolation')."""

    def __init__(
        self,
        adapter_factory: AdapterFactory,
        *,
        download_manager: DownloadManager | None = None,
        max_sessions: int = 4,
        max_tabs_per_session: int = 12,
    ) -> None:
        self._adapter_factory = adapter_factory
        self.registry = BrowserRegistry()
        self.downloads = download_manager or DownloadManager()
        self._active_session_id: str | None = None
        self._max_sessions = max_sessions
        self._max_tabs_per_session = max_tabs_per_session

    def set_adapter_factory(self, factory: AdapterFactory) -> None:
        """Test-only override point — mirrors
        `register_computer_control_tools`'s `bundle` parameter, applied to
        this singleton instead of a freshly constructed one (since
        `browser_manager` is process-global, like every other Phase 7/8
        registry). Never called by any real request path."""
        self._adapter_factory = factory

    async def close_all(self) -> None:
        """Closes every live session's adapter — used both by `main.py`'s
        app-shutdown teardown (a launched Chromium process must never
        outlive this process) and, identically, as the test-isolation
        helper every other process-global registry in this codebase
        needs (see mock_iot.reset_mock_ac_state) so a browser from a
        previous test never leaks into the next one. Bounded by a real
        timeout — a stuck browser/driver process must never hang app
        shutdown (or, in tests, the next test's setup) forever."""
        for session in list(self.registry.list()):
            try:
                await asyncio.wait_for(session.adapter.close(), timeout=10)
            except Exception:
                pass
            self.registry.remove(session.session_id)
        self._active_session_id = None
        self.downloads.reset()

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    def require_session(self, session_id: str | None) -> BrowserSession:
        sid = session_id or self._active_session_id
        if sid is None:
            raise UnknownSessionError("No browser session is active. Call browser.launch first.")
        session = self.registry.get(sid)
        if session is None:
            raise UnknownSessionError(f"Unknown browser session '{sid}'.")
        return session

    def require_tab(self, session: BrowserSession, tab_id: str | None) -> BrowserTab:
        tid = tab_id or session.active_tab_id
        if tid is None or tid not in session.tabs:
            raise UnknownTabError("No active tab in this session.")
        return session.tabs[tid]

    async def launch(
        self, *, headless: bool = True, browser_type: str = "chromium"
    ) -> BrowserSession:
        if len(self.registry.list()) >= self._max_sessions:
            raise BrowserManagerError(
                f"Maximum of {self._max_sessions} concurrent browser sessions reached "
                "(docs/phase-8/PERFORMANCE.md §135 resource limits)."
            )
        adapter = self._adapter_factory()
        session_id = str(uuid4())
        window = BrowserWindow(window_id=str(uuid4()))
        session = BrowserSession(
            session_id=session_id, browser_type=browser_type, adapter=adapter, window=window
        )
        self.registry.add(session)

        async def _on_download(tab_ref: str, event: DownloadEvent) -> None:
            self.downloads.record(session_id=session_id, event=event)

        async def _on_new_tab(_parent_ref: str, new_ref: str) -> None:
            await self._register_tab(session, new_ref, is_popup=True)

        adapter.set_download_handler(_on_download)
        adapter.set_new_tab_handler(_on_new_tab)

        try:
            await adapter.launch(headless=headless)
        except AdapterError:
            session.state = BrowserState.CRASHED
            raise
        session.state = BrowserState.READY
        await self._register_tab(session, await adapter.new_tab())
        self._active_session_id = session_id
        return session

    async def close(self, session_id: str | None = None) -> None:
        session = self.require_session(session_id)
        await session.adapter.close()
        session.state = BrowserState.CLOSED
        self.registry.remove(session.session_id)
        if self._active_session_id == session.session_id:
            remaining = self.registry.list()
            self._active_session_id = remaining[0].session_id if remaining else None

    def focus(self, session_id: str) -> BrowserSession:
        session = self.require_session(session_id)
        self._active_session_id = session.session_id
        session.touch()
        return session

    async def _register_tab(
        self, session: BrowserSession, tab_ref: str, *, is_popup: bool = False
    ) -> str:
        tab_id = str(uuid4())
        url = await session.adapter.get_url(tab_ref)
        title = await session.adapter.get_title(tab_ref)
        tab = BrowserTab(tab_id=tab_id, tab_ref=tab_ref, title=title, url=url, is_popup=is_popup)
        session.tabs[tab_id] = tab
        session.window.tab_ids.append(tab_id)
        session.active_tab_id = tab_id
        session.touch()
        return tab_id

    async def new_tab(self, session_id: str | None, *, url: str | None = None) -> BrowserTab:
        session = self.require_session(session_id)
        if len(session.tabs) >= self._max_tabs_per_session:
            raise BrowserManagerError(
                f"Maximum of {self._max_tabs_per_session} tabs per session reached "
                "(docs/phase-8/PERFORMANCE.md §135 resource limits)."
            )
        tab_ref = await session.adapter.new_tab(url=url)
        tab_id = await self._register_tab(session, tab_ref)
        return session.tabs[tab_id]

    async def close_tab(self, session_id: str | None, tab_id: str) -> None:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        await session.adapter.close_tab(tab.tab_ref)
        del session.tabs[tab_id]
        if tab_id in session.window.tab_ids:
            session.window.tab_ids.remove(tab_id)
        if session.active_tab_id == tab_id:
            remaining = list(session.tabs.keys())
            session.active_tab_id = remaining[0] if remaining else None
        session.touch()

    def list_tabs(self, session_id: str | None) -> list[BrowserTab]:
        session = self.require_session(session_id)
        return list(session.tabs.values())

    def switch_tab(self, session_id: str | None, tab_id: str) -> BrowserTab:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        session.active_tab_id = tab.tab_id
        session.touch()
        return tab

    def current_tab(self, session_id: str | None) -> BrowserTab:
        session = self.require_session(session_id)
        return self.require_tab(session, None)

    def find_tab(self, session_id: str | None, query: str) -> BrowserTab | None:
        """brief §47 — semantic search by title/URL/domain substring, the
        one honest implementation of "find the tab I was looking at"
        without inventing embeddings this phase doesn't need."""
        session = self.require_session(session_id)
        needle = query.strip().lower()
        if not needle:
            return None
        for tab in session.tabs.values():
            haystack = f"{tab.title} {tab.url} {tab.domain}".lower()
            if needle in haystack:
                return tab
        return None

    async def navigate(
        self, session_id: str | None, tab_id: str | None, url: str
    ) -> tuple[BrowserTab, NavigationResult]:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        result = await session.adapter.navigate(tab.tab_ref, url)
        tab.url = result.final_url
        tab.title = result.title
        tab.status = "complete" if result.ok else "crashed"
        session.touch()
        return tab, result

    async def go_back(
        self, session_id: str | None, tab_id: str | None
    ) -> tuple[BrowserTab, NavigationResult]:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        result = await session.adapter.go_back(tab.tab_ref)
        tab.url, tab.title = result.final_url, result.title
        session.touch()
        return tab, result

    async def go_forward(
        self, session_id: str | None, tab_id: str | None
    ) -> tuple[BrowserTab, NavigationResult]:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        result = await session.adapter.go_forward(tab.tab_ref)
        tab.url, tab.title = result.final_url, result.title
        session.touch()
        return tab, result

    async def reload(
        self, session_id: str | None, tab_id: str | None
    ) -> tuple[BrowserTab, NavigationResult]:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        result = await session.adapter.reload(tab.tab_ref)
        tab.url, tab.title = result.final_url, result.title
        session.touch()
        return tab, result

    async def stop_loading(self, session_id: str | None, tab_id: str | None) -> BrowserTab:
        session = self.require_session(session_id)
        tab = self.require_tab(session, tab_id)
        await session.adapter.stop_loading(tab.tab_ref)
        return tab

    def session_for_tab(self, tab_id: str) -> BrowserSession | None:
        for session in self.registry.list():
            if tab_id in session.tabs:
                return session
        return None

    def resolve_tab_target(self, target: str | None) -> tuple[BrowserSession, BrowserTab]:
        """The one place every tab-scoped tool executor (tools.py)
        resolves a `ToolCallRequest.target` — when given, it names a
        tab_id, and the *owning* session is used (not necessarily the
        active one, so a research workflow can act on a background tab);
        when omitted, falls back to the active session's active tab."""
        if target is None:
            session = self.require_session(None)
            return session, self.require_tab(session, None)
        owner = self.session_for_tab(target)
        if owner is None:
            raise UnknownTabError(f"Unknown tab '{target}'.")
        return owner, self.require_tab(owner, target)

    def domain_trust(self, _domain: str) -> DomainTrustStatus:
        """brief §92 — 'do not automatically trust new domains.' No
        persisted allow-list exists yet in this phase (nothing writes
        anything but UNKNOWN), so every domain is honestly UNKNOWN until a
        future phase adds a real, user-editable trust store."""
        return DomainTrustStatus.UNKNOWN


def _default_adapter_factory() -> BrowserAdapter:
    """Reads `Settings` fresh on every call (never cached at import time)
    so a test overriding `VEYRA_BROWSER_DOWNLOADS_DIR` before
    `get_settings.cache_clear()` is honored on the very next
    `browser_manager.launch()` — same discipline `credential_manager`'s
    own `_build_default_store()` already applies."""
    from app.core.config import get_settings
    from app.services.browser.adapter import PlaywrightBrowserAdapter

    return PlaywrightBrowserAdapter(downloads_dir=get_settings().browser_downloads_dir)


# Process-wide singleton, like `tool_registry`/`integration_registry`/
# `device_pairing_service` before it (see this module's own docstring).
browser_manager = BrowserManager(_default_adapter_factory)
