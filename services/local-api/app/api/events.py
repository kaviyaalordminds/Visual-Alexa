"""WebSocket /events — fan-out for the EventBus. docs/architecture/12-EVENTS.md.

Phase 9 audit P1-4: this loop used to block forever on `queue.get()`, so a
connection that had gone silently dead (client vanished without a clean
close — the common case for a laptop sleeping or a network drop) was
invisible to the server until something eventually failed. It now polls
with a timeout and sends an application-level heartbeat frame on each
timeout; `send_text` raising on a truly dead socket is what actually
surfaces the disconnect and lets `finally` unsubscribe it, instead of the
queue sitting there accumulating events for a reader that will never come
back (see event_bus.py's bounded-queue fix for the other half of that).

Phase 10 P1-5 (docs/phase-10/PRODUCTION-AUDIT.md — "no explicit close-all-
websockets step" on shutdown): `_active_connections` tracks every open
`/events` socket so `close_all_websockets()` (called from `app.main`'s
shutdown) can tell each one to close cleanly instead of just letting the
ASGI server tear the process down out from under them.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

HEARTBEAT_INTERVAL_SECONDS = 20.0

_active_connections: set[WebSocket] = set()
_active_connections_lock = asyncio.Lock()


async def close_all_websockets() -> None:
    """Best-effort: a connection already mid-teardown for its own reasons
    (client disconnected a moment ago) may raise here — that's fine, it
    was going to close anyway. Never let one stuck connection block the
    rest from being told to close."""
    async with _active_connections_lock:
        connections = list(_active_connections)
    for websocket in connections:
        try:
            await websocket.close()
        except Exception:
            logger.debug(
                "[VEYRA] /events: error closing a connection during shutdown", exc_info=True
            )


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await event_bus.subscribe()
    async with _active_connections_lock:
        _active_connections.add(websocket)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
            except TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
                continue
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    except Exception:
        # Any other failure (e.g. sending on a socket that died without a
        # clean WebSocketDisconnect) ends this connection's loop the same
        # way — it must never take the whole event bus or other
        # subscribers down with it.
        logger.info("[VEYRA] /events: connection ended unexpectedly", exc_info=True)
    finally:
        await event_bus.unsubscribe(queue)
        async with _active_connections_lock:
            _active_connections.discard(websocket)
