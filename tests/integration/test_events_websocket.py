"""GET/WS /events — Phase 9 audit P1-4: the connection must send a
heartbeat frame when nothing else is happening (so a silently-dead
connection is eventually detected instead of accumulating events for a
reader that never comes back), and must still deliver a real event when
one is published. Exercises the real `events_ws` handler function
directly against a fake WebSocket, deliberately bypassing the ASGI
transport/lifespan machinery (unnecessary for this handler, which touches
only the in-process EventBus, never the database).
"""

from __future__ import annotations

import asyncio
import json

from app.api import events as events_module
from app.core.event_bus import event_bus
from fastapi import WebSocketDisconnect
from veyra_contracts import Event, EventType


class _FakeWebSocket:
    def __init__(self, disconnect_after: int):
        self.sent: list[str] = []
        self._disconnect_after = disconnect_after
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        self.sent.append(data)
        if len(self.sent) >= self._disconnect_after:
            raise WebSocketDisconnect()


async def test_heartbeat_is_sent_when_no_events_are_published(monkeypatch):
    monkeypatch.setattr(events_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    ws = _FakeWebSocket(disconnect_after=3)

    await events_module.events_ws(ws)

    assert ws.accepted
    assert len(ws.sent) == 3
    for frame in ws.sent:
        assert json.loads(frame) == {"type": "heartbeat"}


async def test_a_real_published_event_is_still_delivered_alongside_heartbeats(monkeypatch):
    monkeypatch.setattr(events_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    ws = _FakeWebSocket(disconnect_after=2)

    async def _publish_soon():
        await asyncio.sleep(0.005)
        await event_bus.publish(
            Event(type=EventType.TASK_COMPLETED, correlation_id="corr-1", payload={"ok": True})
        )

    publisher = asyncio.create_task(_publish_soon())
    await events_module.events_ws(ws)
    await publisher

    frames = [json.loads(f) for f in ws.sent]
    real_events = [f for f in frames if f.get("type") != "heartbeat"]
    assert any(f.get("correlation_id") == "corr-1" for f in real_events)


async def test_unsubscribes_on_disconnect_so_the_bus_does_not_leak_subscribers(monkeypatch):
    monkeypatch.setattr(events_module, "HEARTBEAT_INTERVAL_SECONDS", 0.01)
    ws = _FakeWebSocket(disconnect_after=1)
    before = len(event_bus._subscribers)

    await events_module.events_ws(ws)

    assert len(event_bus._subscribers) == before
