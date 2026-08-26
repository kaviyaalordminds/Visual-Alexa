"""In-process EventBus + WebSocket fan-out. docs/architecture/12-EVENTS.md

Phase 1 implements the EventBus interface as an in-process publisher; a
future phase may swap in a message broker without changing any
publisher/subscriber code, because both depend only on this interface.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from veyra_contracts import Event, EventType

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        logger.info(
            "event.published", extra={"event_type": event.type, "event_id": event.id}
        )
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put(event)

    async def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    async def publish_type(
        self, event_type: EventType, correlation_id: str, payload: dict[str, Any] | None = None
    ) -> Event:
        event = Event(type=event_type, correlation_id=correlation_id, payload=payload or {})
        await self.publish(event)
        return event


event_bus = EventBus()
