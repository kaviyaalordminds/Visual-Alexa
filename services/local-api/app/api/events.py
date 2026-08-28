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


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await event_bus.subscribe()
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
