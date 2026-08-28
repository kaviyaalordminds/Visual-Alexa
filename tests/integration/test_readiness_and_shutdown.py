"""GET /ready + shutdown behavior. Phase 10 P1 (docs/phase-10/PRODUCTION-
AUDIT.md): a distinct readiness signal, and a real close-all for open
WebSocket connections on shutdown, neither of which existed before.
"""

from __future__ import annotations

import asyncio
import json

from app.api import events as events_module
from app.core import readiness
from fastapi import WebSocketDisconnect


async def test_ready_endpoint_reports_true_once_the_test_app_state_is_set_up(client):
    # The `client` fixture doesn't run the real lifespan (see
    # tests/conftest.py's own comment on why) — it calls mark_ready()
    # itself here to prove the endpoint's status-code/body contract
    # directly, independent of the full startup sequence (already
    # covered end-to-end by tests/integration/test_backend_startup.py).
    readiness.mark_ready()
    try:
        resp = await client.get("/ready")
        assert resp.status_code == 200
        assert resp.json() == {"ready": True}
    finally:
        readiness.mark_not_ready()


async def test_ready_endpoint_reports_503_before_startup_completes(client):
    readiness.mark_not_ready()
    resp = await client.get("/ready")
    assert resp.status_code == 503
    assert resp.json() == {"ready": False}


def test_uptime_is_none_before_started_and_positive_after():
    readiness._started_at = None
    assert readiness.uptime_seconds() is None
    readiness.mark_started()
    assert readiness.uptime_seconds() is not None
    assert readiness.uptime_seconds() >= 0


class _FakeWebSocket:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


async def test_close_all_websockets_closes_every_tracked_connection():
    fake_a, fake_b = _FakeWebSocket(), _FakeWebSocket()
    events_module._active_connections.add(fake_a)
    events_module._active_connections.add(fake_b)
    try:
        await events_module.close_all_websockets()
        assert fake_a.closed
        assert fake_b.closed
    finally:
        events_module._active_connections.clear()


async def test_close_all_websockets_survives_one_connection_failing_to_close():
    class _Broken:
        async def close(self):
            raise RuntimeError("already gone")

    healthy = _FakeWebSocket()
    events_module._active_connections.add(_Broken())
    events_module._active_connections.add(healthy)
    try:
        await events_module.close_all_websockets()  # must not raise
        assert healthy.closed
    finally:
        events_module._active_connections.clear()


async def test_events_ws_registers_and_unregisters_itself_for_shutdown_close_all():
    class _OneShotWebSocket:
        def __init__(self):
            self.accepted = False
            self.sent = []

        async def accept(self):
            self.accepted = True

        async def send_text(self, data):
            self.sent.append(data)
            raise WebSocketDisconnect()

    ws = _OneShotWebSocket()
    before = len(events_module._active_connections)

    from app.core.event_bus import event_bus
    from veyra_contracts import Event, EventType

    async def _publish_soon():
        await asyncio.sleep(0.005)
        await event_bus.publish(
            Event(type=EventType.TASK_COMPLETED, correlation_id="c", payload={})
        )

    publisher = asyncio.create_task(_publish_soon())
    await events_module.events_ws(ws)
    await publisher

    assert ws.accepted
    assert json.loads(ws.sent[0])["correlation_id"] == "c"
    assert len(events_module._active_connections) == before
