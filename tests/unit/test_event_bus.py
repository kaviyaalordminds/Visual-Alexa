"""EventBus — Phase 9 audit P1-5: subscriber queues must be bounded, with
a defined drop policy for a slow/dead consumer, rather than growing
without limit.
"""

from __future__ import annotations

import asyncio

import pytest
from app.core.event_bus import _MAX_SUBSCRIBER_QUEUE_SIZE, EventBus
from veyra_contracts import Event, EventType


def _event(n: int) -> Event:
    return Event(type=EventType.TASK_PROGRESS, correlation_id=f"corr-{n}", payload={"n": n})


@pytest.mark.asyncio
async def test_subscriber_queue_is_bounded():
    bus = EventBus()
    queue = await bus.subscribe()
    assert queue.maxsize == _MAX_SUBSCRIBER_QUEUE_SIZE


@pytest.mark.asyncio
async def test_a_slow_subscriber_does_not_grow_the_queue_without_bound():
    bus = EventBus()
    queue = await bus.subscribe()  # never read from — simulates a stalled consumer

    for n in range(_MAX_SUBSCRIBER_QUEUE_SIZE + 50):
        await bus.publish(_event(n))

    assert queue.qsize() == _MAX_SUBSCRIBER_QUEUE_SIZE


@pytest.mark.asyncio
async def test_overflow_drops_the_oldest_event_so_the_newest_state_wins():
    bus = EventBus()
    queue = await bus.subscribe()

    total = _MAX_SUBSCRIBER_QUEUE_SIZE + 10
    for n in range(total):
        await bus.publish(_event(n))

    # The oldest events (0..9) must have been dropped to make room; the
    # most recent one published must be the last thing in the queue.
    drained = []
    while not queue.empty():
        drained.append(queue.get_nowait())

    assert len(drained) == _MAX_SUBSCRIBER_QUEUE_SIZE
    assert drained[0].payload["n"] == 10  # the oldest surviving event
    assert drained[-1].payload["n"] == total - 1  # the newest, never dropped


@pytest.mark.asyncio
async def test_one_stalled_subscriber_does_not_block_delivery_to_another():
    bus = EventBus()
    stalled = await bus.subscribe()  # never read
    for _ in range(_MAX_SUBSCRIBER_QUEUE_SIZE + 5):
        await bus.publish(_event(0))

    healthy = await bus.subscribe()
    await bus.publish(_event(999))

    # publish() must not have hung/raised because `stalled` was full.
    received = await asyncio.wait_for(healthy.get(), timeout=1)
    assert received.payload["n"] == 999
    assert stalled.full()
