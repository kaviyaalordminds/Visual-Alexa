"""Interface-only website-adapter stubs. brief §69-70/§171 (Stop
Condition): "Do NOT fully implement Gmail/WhatsApp/Spotify... Instead
create the architecture needed to support them." Mirrors
`app/services/future_adapters.py`'s established shape exactly: every
method raises `NotImplementedError`, nothing here is imported by
`main.py` or reachable from any tool/HTTP route, and each class exists
only so a future phase has a concrete extension point to implement
against. docs/phase-8/WEB-INTEGRATIONS.md.

A real adapter, when a future phase builds one, is expected to use Phase
7's `IntegrationDefinition`/`IntegrationRegistry` (brief §70: "They must
use Phase 7 integration contracts") to register its capabilities as
ordinary tools — never provider-specific logic living inside
`BrowserEngine` itself (brief §43/§45).
"""

from __future__ import annotations

from typing import Protocol

from app.services.browser.manager import BrowserManager


class WebsiteAdapter(Protocol):
    """What every concrete website adapter below implements — detecting
    whether a tab is currently on the site, and providing the site's own
    semantic action surface on top of the generic `browser.*` tools."""

    site_id: str

    async def detect(self, manager: BrowserManager, tab_id: str) -> bool: ...


class GmailAdapter:
    """brief §43 — 'Prepare email.search/read/compose/attach/send... Use
    the integration layer. Do not implement provider-specific logic
    inside BrowserEngine.' Not implemented in this phase."""

    site_id = "gmail"

    async def detect(self, manager: BrowserManager, tab_id: str) -> bool:
        raise NotImplementedError

    async def search(self, query: str) -> list[dict]:
        raise NotImplementedError

    async def compose(self, *, to: str, subject: str, body: str) -> None:
        raise NotImplementedError


class WhatsAppWebAdapter:
    """brief §44 — 'Prepare browser capability support for WhatsApp Web.
    Do not bypass WhatsApp security. Use authorized user session.' Not
    implemented in this phase; sending would require confirmation per
    Phase 7 policy even once it is."""

    site_id = "whatsapp_web"

    async def detect(self, manager: BrowserManager, tab_id: str) -> bool:
        raise NotImplementedError

    async def search_contact(self, name: str) -> list[dict]:
        raise NotImplementedError

    async def open_chat(self, contact_id: str) -> None:
        raise NotImplementedError

    async def send_message(self, contact_id: str, text: str) -> None:
        raise NotImplementedError


class YouTubeAdapter:
    """brief §45/§70 — 'Browser engine must support YouTube... Tools:
    media.search/play/pause/next. Provider-specific implementations
    remain integrations.' Not implemented in this phase — `browser.search`
    + `browser.click`/`browser.find` already cover "search YouTube and
    open a result" generically; this adapter is the extension point for a
    richer, YouTube-specific surface later."""

    site_id = "youtube"

    async def detect(self, manager: BrowserManager, tab_id: str) -> bool:
        raise NotImplementedError

    async def play(self, query: str) -> None:
        raise NotImplementedError

    async def pause(self) -> None:
        raise NotImplementedError

    async def next_track(self) -> None:
        raise NotImplementedError
