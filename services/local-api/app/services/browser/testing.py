"""FakeBrowserAdapter — a deterministic, in-memory stand-in for
`PlaywrightBrowserAdapter`, mirroring the existing
`computer_control.testing`/`vision.testing` fake-backend precedent
(docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2). Lets the orchestration
logic in `manager.py`/`elements.py`/`workflow.py`/`tools.py` be exercised
fast and deterministically, without a real Chromium process, in every
test that doesn't specifically need one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.browser.adapter import (
    DownloadEvent,
    NavigationResult,
    OnDownload,
    OnNewTab,
    RawElement,
)


@dataclass
class FakePage:
    title: str = ""
    elements: list[RawElement] = field(default_factory=list)
    text: str = ""
    outline: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    redirect_to: str | None = None  # simulate a server redirect


@dataclass
class _FakeTab:
    tab_ref: str
    url: str = "about:blank"


class FakeBrowserAdapter:
    """`pages` maps URL -> FakePage; navigating to an unregistered URL
    yields a generic empty page rather than raising, matching how a real
    browser never refuses to load an unknown-but-reachable URL."""

    def __init__(self) -> None:
        self.pages: dict[str, FakePage] = {}
        self._tabs: dict[str, _FakeTab] = {}
        self._next_ref = 0
        self._alive = False
        self.clicked_refs: list[str] = []
        self.typed: list[tuple[str, str]] = []
        self.uploaded: list[tuple[str, str]] = []
        self.clipboard = ""
        self._on_download: OnDownload | None = None
        self._on_new_tab: OnNewTab | None = None

    def add_page(self, url: str, page: FakePage) -> None:
        self.pages[url] = page

    def set_download_handler(self, handler: OnDownload) -> None:
        self._on_download = handler

    def set_new_tab_handler(self, handler: OnNewTab) -> None:
        self._on_new_tab = handler

    async def launch(self, *, headless: bool = True) -> None:
        self._alive = True

    async def close(self) -> None:
        self._alive = False
        self._tabs.clear()

    async def is_alive(self) -> bool:
        return self._alive

    def _allocate_ref(self) -> str:
        self._next_ref += 1
        return f"fake-tab-{self._next_ref}"

    async def new_tab(self, *, url: str | None = None) -> str:
        ref = self._allocate_ref()
        self._tabs[ref] = _FakeTab(tab_ref=ref)
        if url:
            await self.navigate(ref, url)
        return ref

    async def close_tab(self, tab_ref: str) -> None:
        self._tabs.pop(tab_ref, None)

    async def list_tab_refs(self) -> list[str]:
        return list(self._tabs.keys())

    def _page(self, tab_ref: str) -> FakePage:
        url = self._tabs[tab_ref].url
        return self.pages.get(url, FakePage())

    async def navigate(self, tab_ref: str, url: str) -> NavigationResult:
        tab = self._tabs[tab_ref]
        redirects = [url]
        page = self.pages.get(url)
        final_url = url
        if page is not None and page.redirect_to:
            final_url = page.redirect_to
            redirects.append(final_url)
        tab.url = final_url
        resolved = self.pages.get(final_url, FakePage())
        return NavigationResult(
            requested_url=url,
            final_url=final_url,
            redirect_chain=tuple(redirects),
            title=resolved.title,
            ok=True,
            status=200,
        )

    async def go_back(self, tab_ref: str) -> NavigationResult:
        tab = self._tabs[tab_ref]
        return NavigationResult(tab.url, tab.url, (), self._page(tab_ref).title, True)

    async def go_forward(self, tab_ref: str) -> NavigationResult:
        return await self.go_back(tab_ref)

    async def reload(self, tab_ref: str) -> NavigationResult:
        return await self.go_back(tab_ref)

    async def stop_loading(self, tab_ref: str) -> None:
        return None

    async def get_title(self, tab_ref: str) -> str:
        return self._page(tab_ref).title

    async def get_url(self, tab_ref: str) -> str:
        return self._tabs[tab_ref].url

    async def get_loading_state(self, tab_ref: str) -> str:
        return "complete"

    async def query_interactive_elements(self, tab_ref: str) -> list[RawElement]:
        return list(self._page(tab_ref).elements)

    async def list_links(self, tab_ref: str, *, max_links: int = 40) -> list[tuple[str, str]]:
        return list(self._page(tab_ref).links[:max_links])

    async def get_dom_outline(self, tab_ref: str, *, max_nodes: int = 60) -> list[str]:
        return self._page(tab_ref).outline[:max_nodes]

    async def get_visible_text(self, tab_ref: str, *, max_chars: int = 4000) -> str:
        return self._page(tab_ref).text[:max_chars]

    async def click(self, tab_ref: str, element_ref: str) -> None:
        self.clicked_refs.append(element_ref)

    async def click_coordinates(self, tab_ref: str, x: float, y: float) -> None:
        self.clicked_refs.append(f"coord:{x},{y}")

    async def type_text(self, tab_ref: str, element_ref: str, text: str) -> None:
        self.typed.append((element_ref, text))

    async def press_key(self, tab_ref: str, key: str, *, element_ref: str | None = None) -> None:
        return None

    async def select_option(self, tab_ref: str, element_ref: str, value: str) -> None:
        return None

    async def scroll(self, tab_ref: str, *, dy: int, element_ref: str | None = None) -> None:
        return None

    async def scroll_into_view(self, tab_ref: str, element_ref: str) -> None:
        return None

    async def wait_for_selector(
        self, tab_ref: str, element_ref: str, *, timeout_ms: int = 5000
    ) -> bool:
        return any(e.element_ref == element_ref for e in self._page(tab_ref).elements)

    async def wait_for_load(self, tab_ref: str, *, timeout_ms: int = 10000) -> bool:
        return True

    async def screenshot_png_base64(self, tab_ref: str) -> str:
        # A real, tiny, valid 1x1 PNG so OCR-fallback code paths that
        # decode the image don't crash on garbage bytes.
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBA"
            "d8jHAAAAABJRU5ErkJggg=="
        )

    async def upload_file(self, tab_ref: str, element_ref: str, file_path: str) -> None:
        self.uploaded.append((element_ref, file_path))

    async def fetch_bytes(self, tab_ref: str, url: str) -> tuple[bytes, str | None]:
        page = self.pages.get(url)
        if page is not None:
            return page.text.encode("utf-8"), "text/plain"
        return b"", None

    async def clipboard_read(self, tab_ref: str) -> str:
        return self.clipboard

    async def clipboard_write(self, tab_ref: str, text: str) -> None:
        self.clipboard = text

    # --- test-only simulation hooks (never called by real code) ---

    async def simulate_download(
        self, tab_ref: str, *, filename: str, source_url: str, ok: bool = True
    ) -> None:
        if self._on_download is not None:
            await self._on_download(
                tab_ref,
                DownloadEvent(
                    filename=filename,
                    source_url=source_url,
                    destination_path=f"/fake/downloads/{filename}" if ok else None,
                    size_bytes=1024 if ok else None,
                    ok=ok,
                    error=None if ok else "simulated failure",
                ),
            )

    async def simulate_popup(self, parent_ref: str, *, url: str) -> str:
        ref = self._allocate_ref()
        self._tabs[ref] = _FakeTab(tab_ref=ref, url=url)
        if self._on_new_tab is not None:
            await self._on_new_tab(parent_ref, ref)
        return ref
