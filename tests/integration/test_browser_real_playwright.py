"""Real, end-to-end test against a genuine headless Chromium process
(not `FakeBrowserAdapter`) and a real local HTTP test website
(`tests/fixtures/browser_test_site.py`, brief §145). Proves the
`PlaywrightBrowserAdapter` actually drives a browser, not just that the
orchestration logic around a fake one is correct — the reference
workflows brief §172 asks for (A/B-ish/C/E/F-ish/G/H/I/J; D is covered
for real by `test_browser_manager.py::test_find_tab_matches_title_url_or_domain`
against the fake adapter, since `find_tab` needs no real browser to
prove).

Deliberately ONE test function launching ONE real browser session (using
separate tabs for isolation between scenarios): a real bug this suite's
own verification found is that launching a *second* real Playwright
driver process later in the same pytest session (even from a different
test function, even after the first was fully closed) reliably hangs —
reproduced directly with a minimal two-test repro, isolated to two
sequential `async_playwright().start()` calls sharing pytest-asyncio's
session-scoped event loop (`pytest.ini`'s own documented reason for that
scoping), not to anything in `BrowserManager`/`PlaywrightBrowserAdapter`
itself (a plain `asyncio.run()` script launching/closing twice in a row
works fine). Documented here rather than silently worked around, per
docs/phase-8/PHASE-8-TEST-RESULTS.md's "real bugs found" section.

Skips (never fails) if this environment's pre-installed Chromium binary
isn't at the expected sandbox path — real deployments resolve their own
managed browser via `PlaywrightBrowserAdapter(downloads_dir=...)` with no
`executable_path` override at all (see `manager.py::_default_adapter_factory`).
"""

from __future__ import annotations

import asyncio
import base64
import os

import pytest
from app.core.config import get_settings
from app.services.browser.adapter import PlaywrightBrowserAdapter
from app.services.browser.manager import browser_manager

from tests.fixtures.browser_test_site import browser_test_site  # noqa: F401

_SANDBOX_CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

pytestmark = pytest.mark.skipif(
    not os.path.exists(_SANDBOX_CHROME),
    reason="Real Chromium binary not present at the expected sandbox path.",
)


def _real_adapter_factory():
    return PlaywrightBrowserAdapter(
        downloads_dir=get_settings().browser_downloads_dir,
        executable_path=_SANDBOX_CHROME,
        extra_launch_args=["--no-sandbox"],
    )


async def _grant(client, tool_id: str, risk: str = "MODERATE") -> None:
    resp = await client.post(
        "/permissions", json={"tool_id": tool_id, "risk_level": risk, "scope": "ALLOW_SESSION"}
    )
    assert resp.status_code == 201


async def test_real_playwright_end_to_end_workflows(client, browser_test_site):  # noqa: F811
    browser_manager.set_adapter_factory(_real_adapter_factory)
    try:
        # Workflow A: "Open Chrome."
        launch = await client.post("/tools/browser.launch/invoke", json={})
        launch_body = launch.json()
        assert launch_body["status"] == "SUCCESS"
        session_id = launch_body["output"]["session_id"]
        session = browser_manager.registry.get(session_id)
        assert await session.adapter.is_alive()

        # Navigate + find the download button (brief §58/§60 semantic identity)
        nav = await client.post(
            "/tools/browser.navigate/invoke", json={"arguments": {"url": browser_test_site + "/"}}
        )
        assert nav.json()["output"]["title"] == "VEYRA Test Home"
        found = await client.post(
            "/tools/browser.find/invoke", json={"arguments": {"query": "Download PDF"}}
        )
        found_body = found.json()["output"]
        assert found_body["best"] is not None
        assert found_body["best"]["evidence_tier"] == "BROWSER_DOM"

        # Ambiguous target acceptance (brief §14)
        await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/ambiguous"}},
        )
        await _grant(client, "browser.click")
        ambiguous = await client.post(
            "/tools/browser.click/invoke", json={"arguments": {"query": "Submit"}}
        )
        assert ambiguous.json()["error"]["code"] == "AMBIGUOUS_TARGET"

        # Workflow H: fill a non-sensitive test form
        await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/form"}},
        )
        await _grant(client, "browser.fill_form")
        fill = await client.post(
            "/tools/browser.fill_form/invoke",
            json={
                "arguments": {"fields": {"Full Name": "Ada Lovelace", "Email": "ada@example.com"}}
            },
        )
        fill_body = fill.json()["output"]
        assert set(fill_body["filled"]) == {"Full Name", "Email"}
        assert fill_body["skipped"] == []

        # Table extraction (brief §106) + real visible-text extraction
        await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/table"}},
        )
        extract = await client.post("/tools/browser.extract_text/invoke", json={})
        text = extract.json()["output"]["text"]
        assert "Laptop" in text
        assert "999" in text

        # Redirect detection (brief §94)
        redirect = await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/redirect"}},
        )
        redirect_body = redirect.json()["output"]
        assert redirect_body["final_url"] == browser_test_site + "/table"
        assert not redirect_body["suspicious_redirect"]  # same-origin

        # 404 handling (brief §151 failure test)
        missing = await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/missing"}},
        )
        missing_body = missing.json()
        assert missing_body["status"] == "FAILURE"
        assert missing_body["error"]["code"] == "NAVIGATION_FAILED"

        # Dynamic content (brief §55/56) — content genuinely changes after JS timeout
        await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/slow"}},
        )
        immediate = await client.post("/tools/browser.extract_text/invoke", json={})
        assert "pending" in immediate.json()["output"]["text"]
        await asyncio.sleep(0.7)
        later = await client.post("/tools/browser.extract_text/invoke", json={})
        assert "ready" in later.json()["output"]["text"]

        # Workflow E/I: download a real file and verify it landed on disk
        await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/download"}},
        )
        await client.post(
            "/tools/browser.click/invoke", json={"arguments": {"query": "Download Report"}}
        )
        await asyncio.sleep(0.5)  # real download event delivery is async
        downloads = await client.get("/browser/downloads")
        records = downloads.json()["downloads"]
        assert records
        record = records[0]
        assert record["status"] == "completed"
        assert record["destination_path"] is not None
        assert os.path.exists(record["destination_path"])
        assert not record["potentially_dangerous"]

        # Workflow J-ish: back/forward navigation
        await client.post(
            "/tools/browser.navigate/invoke", json={"arguments": {"url": browser_test_site + "/"}}
        )
        await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": browser_test_site + "/table"}},
        )
        back = await client.post("/tools/browser.back/invoke", json={})
        assert back.json()["output"]["url"] == browser_test_site + "/"
        forward = await client.post("/tools/browser.forward/invoke", json={})
        assert forward.json()["output"]["url"] == browser_test_site + "/table"

        # Real screenshot
        await _grant(client, "browser.screenshot")
        screenshot = await client.post("/tools/browser.screenshot/invoke", json={})
        png_bytes = base64.b64decode(screenshot.json()["output"]["image_base64"])
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        await browser_manager.close_all()
