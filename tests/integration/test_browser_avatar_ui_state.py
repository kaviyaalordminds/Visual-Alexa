"""brief §139/§164 — BROWSING/SEARCHING/READING/BLOCKED published over
the same real `voice.ui_state.changed` channel Phase 6 established,
subscribed to the real event_bus exactly like test_avatar_ui_state.py, so
this is end-to-end against the real browser tool executors, never a mock
of them.
"""

from __future__ import annotations

from app.core.event_bus import event_bus
from app.services.browser.adapter import RawElement
from app.services.browser.manager import browser_manager
from app.services.browser.testing import FakePage
from veyra_contracts import EventType


async def _drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def _ui_states(events):
    return [e.payload["agent_state"] for e in events if e.type == EventType.VOICE_UI_STATE_CHANGED]


def _adapter():
    session = browser_manager.registry.get(browser_manager.active_session_id)
    return session.adapter


async def test_navigate_publishes_browsing_state(client):
    await client.post("/tools/browser.launch/invoke", json={})
    _adapter().add_page("https://x/", FakePage(title="X"))
    queue = await event_bus.subscribe()
    try:
        await client.post(
            "/tools/browser.navigate/invoke", json={"arguments": {"url": "https://x/"}}
        )
        events = await _drain(queue)
        assert "BROWSING" in _ui_states(events)
    finally:
        await event_bus.unsubscribe(queue)


async def test_search_publishes_searching_state(client):
    await client.post("/tools/browser.launch/invoke", json={})
    queue = await event_bus.subscribe()
    try:
        await client.post("/tools/browser.search/invoke", json={"arguments": {"query": "laptops"}})
        events = await _drain(queue)
        assert "SEARCHING" in _ui_states(events)
    finally:
        await event_bus.unsubscribe(queue)


async def test_extract_text_publishes_reading_state(client):
    await client.post("/tools/browser.launch/invoke", json={})
    _adapter().add_page("https://x/", FakePage(text="hello"))
    await client.post("/tools/browser.navigate/invoke", json={"arguments": {"url": "https://x/"}})
    queue = await event_bus.subscribe()
    try:
        await client.post("/tools/browser.extract_text/invoke", json={})
        events = await _drain(queue)
        assert "READING" in _ui_states(events)
    finally:
        await event_bus.unsubscribe(queue)


async def test_captcha_stop_publishes_blocked_state(client):
    await client.post("/tools/browser.launch/invoke", json={})
    _adapter().add_page(
        "https://x/",
        FakePage(
            text="Please verify you are human by completing the CAPTCHA below.",
            elements=[
                RawElement(
                    element_ref="1",
                    role="button",
                    tag="button",
                    text="Continue",
                    aria_label=None,
                    placeholder=None,
                    name=None,
                    value=None,
                    visible=True,
                    enabled=True,
                    bounding_box={"x": 0, "y": 0, "width": 20, "height": 10},
                )
            ],
        ),
    )
    await client.post("/tools/browser.navigate/invoke", json={"arguments": {"url": "https://x/"}})
    await client.post(
        "/permissions",
        json={"tool_id": "browser.click", "risk_level": "MODERATE", "scope": "ALLOW_SESSION"},
    )
    queue = await event_bus.subscribe()
    try:
        await client.post("/tools/browser.click/invoke", json={"arguments": {"query": "Continue"}})
        events = await _drain(queue)
        assert "BLOCKED" in _ui_states(events)
    finally:
        await event_bus.unsubscribe(queue)
