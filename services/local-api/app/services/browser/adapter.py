"""BrowserAdapter — the one seam between VEYRA's browser engine and a
real browser engine implementation. docs/phase-8/BROWSER-ADAPTER.md.

brief §3-4: "Do NOT tightly couple the browser engine to Chrome... Create
BrowserAdapter." Every other module in this package (`manager.py`,
`observation.py`, `elements.py`, ...) depends only on the `BrowserAdapter`
Protocol below, never on Playwright directly — `PlaywrightBrowserAdapter`
is the one real implementation, and `testing.FakeBrowserAdapter` is a
second, deterministic one used by the fast unit-test suite. Adding
Firefox/WebKit later (brief §3 "Future: Firefox, other Chromium
browsers") means adding a third adapter, never touching a caller.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RawElement:
    """One candidate interactive element as read directly off the page —
    the raw material `elements.ElementResolver` scores and ranks.
    docs/phase-8/ELEMENT-RESOLUTION.md §12."""

    element_ref: str  # opaque adapter-internal handle (e.g. a stable DOM path)
    role: str | None
    tag: str | None
    text: str | None
    aria_label: str | None
    placeholder: str | None
    name: str | None
    value: str | None
    visible: bool
    enabled: bool
    bounding_box: dict[str, float] | None


@dataclass(frozen=True)
class NavigationResult:
    requested_url: str
    final_url: str
    redirect_chain: tuple[str, ...]
    title: str
    ok: bool
    status: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class DownloadEvent:
    filename: str
    source_url: str
    destination_path: str | None
    size_bytes: int | None
    ok: bool
    error: str | None = None


OnDownload = Callable[[str, DownloadEvent], Awaitable[None]]
"""Called as `on_download(tab_id, event)` — see `manager.BrowserManager`."""
OnNewTab = Callable[[str, str], Awaitable[None]]
"""Called as `on_new_tab(parent_tab_id, new_tab_ref)` when the page itself
opens a new tab/popup (brief §53 'New Window Detection') — the adapter
notifies the manager rather than silently tracking it alone."""


class BrowserAdapter(Protocol):
    """One physical browser process this adapter drives. A
    `BrowserManager` (manager.py) owns one adapter instance per
    `BrowserSession`."""

    async def launch(self, *, headless: bool = True) -> None: ...

    async def close(self) -> None: ...

    async def is_alive(self) -> bool: ...

    async def new_tab(self, *, url: str | None = None) -> str:
        """Returns an opaque tab_ref, stable for the tab's lifetime."""
        ...

    async def close_tab(self, tab_ref: str) -> None: ...

    async def list_tab_refs(self) -> list[str]: ...

    async def navigate(self, tab_ref: str, url: str) -> NavigationResult: ...

    async def go_back(self, tab_ref: str) -> NavigationResult: ...

    async def go_forward(self, tab_ref: str) -> NavigationResult: ...

    async def reload(self, tab_ref: str) -> NavigationResult: ...

    async def stop_loading(self, tab_ref: str) -> None: ...

    async def get_title(self, tab_ref: str) -> str: ...

    async def get_url(self, tab_ref: str) -> str: ...

    async def get_loading_state(self, tab_ref: str) -> str:
        """'loading' | 'complete'."""
        ...

    async def query_interactive_elements(self, tab_ref: str) -> list[RawElement]: ...

    async def list_links(self, tab_ref: str, *, max_links: int = 40) -> list[tuple[str, str]]:
        """(text, absolute href) pairs — the primitive `research.py` uses
        to find real result URLs, distinct from `query_interactive_elements`
        (which never carries href, since no other tool needs it)."""
        ...

    async def get_dom_outline(self, tab_ref: str, *, max_nodes: int = 60) -> list[str]:
        """A short indented outline (brief §11's PAGE tree example) — never
        the full DOM."""
        ...

    async def get_visible_text(self, tab_ref: str, *, max_chars: int = 4000) -> str: ...

    async def click(self, tab_ref: str, element_ref: str) -> None: ...

    async def click_coordinates(self, tab_ref: str, x: float, y: float) -> None: ...

    async def type_text(self, tab_ref: str, element_ref: str, text: str) -> None: ...

    async def press_key(
        self, tab_ref: str, key: str, *, element_ref: str | None = None
    ) -> None: ...

    async def select_option(self, tab_ref: str, element_ref: str, value: str) -> None: ...

    async def scroll(self, tab_ref: str, *, dy: int, element_ref: str | None = None) -> None: ...

    async def scroll_into_view(self, tab_ref: str, element_ref: str) -> None: ...

    async def wait_for_selector(
        self, tab_ref: str, element_ref: str, *, timeout_ms: int = 5000
    ) -> bool: ...

    async def wait_for_load(self, tab_ref: str, *, timeout_ms: int = 10000) -> bool: ...

    async def screenshot_png_base64(self, tab_ref: str) -> str: ...

    async def upload_file(self, tab_ref: str, element_ref: str, file_path: str) -> None: ...

    async def fetch_bytes(self, tab_ref: str, url: str) -> tuple[bytes, str | None]:
        """Direct GET through the browser's own request context (reuses
        cookies/session) — the primitive `browser.download(url)` uses.
        Returns (body, content_type)."""
        ...

    async def clipboard_read(self, tab_ref: str) -> str: ...

    async def clipboard_write(self, tab_ref: str, text: str) -> None: ...

    def set_download_handler(self, handler: OnDownload) -> None: ...

    def set_new_tab_handler(self, handler: OnNewTab) -> None: ...


@dataclass
class _TabState:
    ref: str
    page: Any
    is_popup: bool = False
    opener_ref: str | None = None


class AdapterError(RuntimeError):
    """Raised for any adapter-level failure a caller must map onto a real
    `ErrorCategory` — never leaked past `manager.py`/`tools.py` as a raw
    Playwright exception."""


try:
    from playwright.async_api import Download, Page, async_playwright
    from playwright.async_api import Error as PlaywrightError
except ImportError:  # pragma: no cover - playwright is a declared dependency
    async_playwright = None  # type: ignore[assignment]
    Page = Any  # type: ignore[assignment,misc]
    Download = Any  # type: ignore[assignment,misc]
    PlaywrightError = Exception  # type: ignore[assignment,misc]


class PlaywrightBrowserAdapter:
    """Real implementation, Chromium-first (brief §3). `channel` is the
    one extension point for "Secondary architecture: Microsoft Edge"
    (Playwright's `channel="msedge"`) without this class or any caller
    changing — never hard-code "Chrome" beyond this one constructor
    argument.

    `executable_path`/`extra_launch_args` are deployment-environment
    overrides (e.g. this dev container's pre-installed browser sitting at
    a Playwright-driver revision the pip-installed `playwright` package
    doesn't auto-resolve, needing `--no-sandbox` to run as root) — a
    normal Windows install leaves both `None` and lets Playwright resolve
    its own managed browser exactly as `playwright install` sets up."""

    def __init__(
        self,
        *,
        channel: str | None = None,
        downloads_dir: str | None = None,
        executable_path: str | None = None,
        extra_launch_args: list[str] | None = None,
    ) -> None:
        self._channel = channel
        self._downloads_dir = downloads_dir
        self._executable_path = executable_path
        self._extra_launch_args = extra_launch_args or []
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._tabs: dict[str, _TabState] = {}
        self._next_ref = 0
        self._on_download: OnDownload | None = None
        self._on_new_tab: OnNewTab | None = None

    def set_download_handler(self, handler: OnDownload) -> None:
        self._on_download = handler

    def set_new_tab_handler(self, handler: OnNewTab) -> None:
        self._on_new_tab = handler

    async def launch(self, *, headless: bool = True) -> None:
        if async_playwright is None:
            raise AdapterError("playwright is not installed in this environment.")
        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if self._channel:
            launch_kwargs["channel"] = self._channel
        if self._executable_path:
            launch_kwargs["executable_path"] = self._executable_path
        if self._extra_launch_args:
            launch_kwargs["args"] = self._extra_launch_args
        try:
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        except PlaywrightError as exc:
            await self._playwright.stop()
            self._playwright = None
            raise AdapterError(f"Failed to launch browser: {exc}") from exc
        self._context = await self._browser.new_context(accept_downloads=True)
        self._context.on("page", self._handle_context_new_page)

    async def close(self) -> None:
        self._tabs.clear()
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def is_alive(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    def _allocate_ref(self) -> str:
        self._next_ref += 1
        return f"tab-{self._next_ref}"

    def _register_page(
        self, page: Page, *, is_popup: bool = False, opener_ref: str | None = None
    ) -> str:
        ref = self._allocate_ref()
        self._tabs[ref] = _TabState(ref=ref, page=page, is_popup=is_popup, opener_ref=opener_ref)
        page.on("download", lambda dl: self._handle_download(ref, dl))
        return ref

    async def _handle_context_new_page(self, page: Page) -> None:
        # brief §53 "New Window Detection" — a page opened by the site
        # itself (window.open/target=_blank), not one this adapter's own
        # new_tab() created. new_tab() registers its own page directly, so
        # by the time this fires for a manager-initiated tab it is
        # already tracked; guard against double registration.
        if any(state.page is page for state in self._tabs.values()):
            return
        ref = self._register_page(page, is_popup=True)
        if self._on_new_tab is not None:
            await self._on_new_tab("", ref)

    async def _handle_download(self, tab_ref: str, download: Download) -> None:
        if self._on_download is None:
            return
        try:
            path = None
            if self._downloads_dir:
                import os

                os.makedirs(self._downloads_dir, exist_ok=True)
                path = os.path.join(self._downloads_dir, download.suggested_filename)
                await download.save_as(path)
            event = DownloadEvent(
                filename=download.suggested_filename,
                source_url=download.url,
                destination_path=path,
                size_bytes=None,
                ok=True,
            )
        except PlaywrightError as exc:
            event = DownloadEvent(
                filename=download.suggested_filename,
                source_url=download.url,
                destination_path=None,
                size_bytes=None,
                ok=False,
                error=str(exc),
            )
        await self._on_download(tab_ref, event)

    def _page(self, tab_ref: str) -> Page:
        state = self._tabs.get(tab_ref)
        if state is None:
            raise AdapterError(f"Unknown tab '{tab_ref}'.")
        return state.page

    async def new_tab(self, *, url: str | None = None) -> str:
        if self._context is None:
            raise AdapterError("Browser is not launched.")
        page = await self._context.new_page()
        ref = self._register_page(page)
        if url:
            await self.navigate(ref, url)
        return ref

    async def close_tab(self, tab_ref: str) -> None:
        state = self._tabs.pop(tab_ref, None)
        if state is not None:
            await state.page.close()

    async def list_tab_refs(self) -> list[str]:
        return list(self._tabs.keys())

    async def navigate(self, tab_ref: str, url: str) -> NavigationResult:
        page = self._page(tab_ref)
        redirects: list[str] = []

        def _on_frame_nav(frame: Any) -> None:
            if frame == page.main_frame and frame.url not in redirects:
                redirects.append(frame.url)

        page.on("framenavigated", _on_frame_nav)
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            title = await page.title()
            return NavigationResult(
                requested_url=url,
                final_url=page.url,
                redirect_chain=tuple(redirects),
                title=title,
                ok=response is not None and response.ok,
                status=response.status if response is not None else None,
            )
        except PlaywrightError as exc:
            return NavigationResult(
                requested_url=url,
                final_url=page.url,
                redirect_chain=tuple(redirects),
                title="",
                ok=False,
                error=str(exc),
            )
        finally:
            page.remove_listener("framenavigated", _on_frame_nav)

    async def go_back(self, tab_ref: str) -> NavigationResult:
        page = self._page(tab_ref)
        try:
            response = await page.go_back(wait_until="domcontentloaded")
            return NavigationResult(
                requested_url=page.url,
                final_url=page.url,
                redirect_chain=(),
                title=await page.title(),
                ok=response is not None and response.ok if response else True,
            )
        except PlaywrightError as exc:
            return NavigationResult(
                requested_url=page.url,
                final_url=page.url,
                redirect_chain=(),
                title="",
                ok=False,
                error=str(exc),
            )

    async def go_forward(self, tab_ref: str) -> NavigationResult:
        page = self._page(tab_ref)
        try:
            response = await page.go_forward(wait_until="domcontentloaded")
            return NavigationResult(
                requested_url=page.url,
                final_url=page.url,
                redirect_chain=(),
                title=await page.title(),
                ok=response is not None and response.ok if response else True,
            )
        except PlaywrightError as exc:
            return NavigationResult(
                requested_url=page.url,
                final_url=page.url,
                redirect_chain=(),
                title="",
                ok=False,
                error=str(exc),
            )

    async def reload(self, tab_ref: str) -> NavigationResult:
        page = self._page(tab_ref)
        try:
            response = await page.reload(wait_until="domcontentloaded")
            return NavigationResult(
                requested_url=page.url,
                final_url=page.url,
                redirect_chain=(),
                title=await page.title(),
                ok=response is not None and response.ok if response else True,
            )
        except PlaywrightError as exc:
            return NavigationResult(
                requested_url=page.url,
                final_url=page.url,
                redirect_chain=(),
                title="",
                ok=False,
                error=str(exc),
            )

    async def stop_loading(self, tab_ref: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.evaluate("window.stop()")
        except PlaywrightError:
            pass

    async def get_title(self, tab_ref: str) -> str:
        return await self._page(tab_ref).title()

    async def get_url(self, tab_ref: str) -> str:
        return self._page(tab_ref).url

    async def get_loading_state(self, tab_ref: str) -> str:
        page = self._page(tab_ref)
        try:
            state = await page.evaluate("document.readyState")
        except PlaywrightError:
            return "loading"
        return "complete" if state == "complete" else "loading"

    _INTERACTIVE_JS = """
    () => {
      const nodes = Array.from(document.querySelectorAll(
        'a, button, input, textarea, select, [role="button"], [role="link"], '
        + '[role="checkbox"], [role="radio"], [role="menuitem"], [onclick], [tabindex]'
      ));
      return nodes.slice(0, 200).map((el, i) => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const visible = rect.width > 0 && rect.height > 0
          && style.visibility !== 'hidden' && style.display !== 'none';
        el.setAttribute('data-veyra-ref', String(i));
        return {
          element_ref: String(i),
          role: el.getAttribute('role') || el.tagName.toLowerCase(),
          tag: el.tagName.toLowerCase(),
          text: (el.innerText || el.value || '').trim().slice(0, 200) || null,
          aria_label: el.getAttribute('aria-label'),
          placeholder: el.getAttribute('placeholder'),
          name: el.getAttribute('name'),
          value: el.value !== undefined ? String(el.value).slice(0, 200) : null,
          visible: visible,
          enabled: !el.disabled,
          bounding_box: visible
            ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
            : null,
        };
      });
    }
    """

    async def query_interactive_elements(self, tab_ref: str) -> list[RawElement]:
        page = self._page(tab_ref)
        try:
            raw = await page.evaluate(self._INTERACTIVE_JS)
        except PlaywrightError as exc:
            raise AdapterError(f"Failed to query elements: {exc}") from exc
        return [
            RawElement(
                element_ref=item["element_ref"],
                role=item.get("role"),
                tag=item.get("tag"),
                text=item.get("text"),
                aria_label=item.get("aria_label"),
                placeholder=item.get("placeholder"),
                name=item.get("name"),
                value=item.get("value"),
                visible=bool(item.get("visible")),
                enabled=bool(item.get("enabled")),
                bounding_box=item.get("bounding_box"),
            )
            for item in raw
        ]

    async def list_links(self, tab_ref: str, *, max_links: int = 40) -> list[tuple[str, str]]:
        page = self._page(tab_ref)
        script = """
        (maxLinks) => Array.from(document.querySelectorAll('a[href]'))
          .slice(0, maxLinks)
          .map((a) => [(a.innerText || '').trim().slice(0, 200), a.href])
          .filter(([, href]) => href.startsWith('http'))
        """
        try:
            pairs = await page.evaluate(script, max_links)
        except PlaywrightError as exc:
            raise AdapterError(f"Failed to list links: {exc}") from exc
        return [(text, href) for text, href in pairs]

    async def get_dom_outline(self, tab_ref: str, *, max_nodes: int = 60) -> list[str]:
        page = self._page(tab_ref)
        script = """
        (maxNodes) => {
          const landmarks = Array.from(document.querySelectorAll(
            'header, nav, main, footer, form, section, article, aside, h1, h2, h3, '
            + 'button, a, input, [role]'
          )).slice(0, maxNodes);
          return landmarks.map((el) => {
            const label = el.getAttribute('aria-label') || el.innerText?.trim().slice(0, 40) || '';
            return `${el.tagName.toLowerCase()}${label ? ': ' + label : ''}`;
          });
        }
        """
        try:
            return await page.evaluate(script, max_nodes)
        except PlaywrightError as exc:
            raise AdapterError(f"Failed to build DOM outline: {exc}") from exc

    async def get_visible_text(self, tab_ref: str, *, max_chars: int = 4000) -> str:
        page = self._page(tab_ref)
        try:
            text = await page.evaluate("document.body ? document.body.innerText : ''")
        except PlaywrightError as exc:
            raise AdapterError(f"Failed to read page text: {exc}") from exc
        return (text or "")[:max_chars]

    def _selector_for(self, element_ref: str) -> str:
        return f'[data-veyra-ref="{element_ref}"]'

    async def click(self, tab_ref: str, element_ref: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.click(self._selector_for(element_ref), timeout=5000)
        except PlaywrightError as exc:
            raise AdapterError(f"Click failed: {exc}") from exc

    async def click_coordinates(self, tab_ref: str, x: float, y: float) -> None:
        page = self._page(tab_ref)
        try:
            await page.mouse.click(x, y)
        except PlaywrightError as exc:
            raise AdapterError(f"Coordinate click failed: {exc}") from exc

    async def type_text(self, tab_ref: str, element_ref: str, text: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.fill(self._selector_for(element_ref), text, timeout=5000)
        except PlaywrightError as exc:
            raise AdapterError(f"Type failed: {exc}") from exc

    async def press_key(self, tab_ref: str, key: str, *, element_ref: str | None = None) -> None:
        page = self._page(tab_ref)
        try:
            if element_ref:
                await page.press(self._selector_for(element_ref), key, timeout=5000)
            else:
                await page.keyboard.press(key)
        except PlaywrightError as exc:
            raise AdapterError(f"Key press failed: {exc}") from exc

    async def select_option(self, tab_ref: str, element_ref: str, value: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.select_option(self._selector_for(element_ref), value, timeout=5000)
        except PlaywrightError as exc:
            raise AdapterError(f"Select failed: {exc}") from exc

    async def scroll(self, tab_ref: str, *, dy: int, element_ref: str | None = None) -> None:
        page = self._page(tab_ref)
        try:
            if element_ref:
                await page.eval_on_selector(
                    self._selector_for(element_ref), "(el, dy) => el.scrollBy(0, dy)", dy
                )
            else:
                await page.mouse.wheel(0, dy)
        except PlaywrightError as exc:
            raise AdapterError(f"Scroll failed: {exc}") from exc

    async def scroll_into_view(self, tab_ref: str, element_ref: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.eval_on_selector(
                self._selector_for(element_ref), "(el) => el.scrollIntoView({block: 'center'})"
            )
        except PlaywrightError as exc:
            raise AdapterError(f"Scroll into view failed: {exc}") from exc

    async def wait_for_selector(
        self, tab_ref: str, element_ref: str, *, timeout_ms: int = 5000
    ) -> bool:
        page = self._page(tab_ref)
        try:
            await page.wait_for_selector(self._selector_for(element_ref), timeout=timeout_ms)
            return True
        except PlaywrightError:
            return False

    async def wait_for_load(self, tab_ref: str, *, timeout_ms: int = 10000) -> bool:
        page = self._page(tab_ref)
        try:
            await page.wait_for_load_state("load", timeout=timeout_ms)
            return True
        except PlaywrightError:
            return False

    async def screenshot_png_base64(self, tab_ref: str) -> str:
        import base64

        page = self._page(tab_ref)
        try:
            data = await page.screenshot(type="png")
        except PlaywrightError as exc:
            raise AdapterError(f"Screenshot failed: {exc}") from exc
        return base64.b64encode(data).decode("ascii")

    async def upload_file(self, tab_ref: str, element_ref: str, file_path: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.set_input_files(self._selector_for(element_ref), file_path)
        except PlaywrightError as exc:
            raise AdapterError(f"Upload failed: {exc}") from exc

    async def fetch_bytes(self, tab_ref: str, url: str) -> tuple[bytes, str | None]:
        page = self._page(tab_ref)
        try:
            response = await page.context.request.get(url)
            body = await response.body()
            return body, response.headers.get("content-type")
        except PlaywrightError as exc:
            raise AdapterError(f"Fetch failed: {exc}") from exc

    async def clipboard_read(self, tab_ref: str) -> str:
        page = self._page(tab_ref)
        try:
            return await page.evaluate("navigator.clipboard.readText()")
        except PlaywrightError as exc:
            raise AdapterError(f"Clipboard read failed: {exc}") from exc

    async def clipboard_write(self, tab_ref: str, text: str) -> None:
        page = self._page(tab_ref)
        try:
            await page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
        except PlaywrightError as exc:
            raise AdapterError(f"Clipboard write failed: {exc}") from exc
