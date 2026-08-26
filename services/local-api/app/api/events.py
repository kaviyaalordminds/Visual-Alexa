"""WebSocket /events — fan-out for the EventBus. docs/architecture/12-EVENTS.md."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


@router.websocket("/events")
async def events_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await event_bus.subscribe()
    try:
        while True:
            event = await queue.get()
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        await event_bus.unsubscribe(queue)
