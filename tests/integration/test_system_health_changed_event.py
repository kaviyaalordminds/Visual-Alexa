"""Phase 13 (docs/phase-13-audit.md §1) — `EventType.SYSTEM_HEALTH_CHANGED`
existed since Phase 1 but was never published anywhere. `GET /system` now
diffs each call's computed status against the previous call's and
publishes only when something real actually changed — never on every
poll (that would make the event meaningless noise), and never on the
very first call after a reset (there is nothing to diff against yet).
"""

from __future__ import annotations

from app.core.event_bus import event_bus
from veyra_contracts import EventType


async def _drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


async def test_first_call_after_reset_never_publishes(client):
    """`_reset_state` already calls `reset_last_status_snapshot()` for
    every test — the very first `/system` poll in a fresh test has
    nothing to diff against and must stay silent."""
    queue = await event_bus.subscribe()
    try:
        resp = await client.get("/system")
        assert resp.status_code == 200
        events = await _drain(queue)
        assert EventType.SYSTEM_HEALTH_CHANGED not in [e.type for e in events]
    finally:
        await event_bus.unsubscribe(queue)


async def test_repeated_polls_with_no_change_never_publish(client):
    queue = await event_bus.subscribe()
    try:
        await client.get("/system")
        await _drain(queue)  # discard whatever the first call did (nothing, per above)

        for _ in range(3):
            resp = await client.get("/system")
            assert resp.status_code == 200
        events = await _drain(queue)
        assert EventType.SYSTEM_HEALTH_CHANGED not in [e.type for e in events]
    finally:
        await event_bus.unsubscribe(queue)


async def test_a_real_status_change_publishes_system_health_changed_with_the_diff(
    client, monkeypatch
):
    """Force `database` to flip CONNECTED -> ERROR between two polls (the
    same real, named check `test_health_system.py` already forces) and
    confirm the event carries exactly what changed."""
    queue = await event_bus.subscribe()
    try:
        first = await client.get("/system")
        assert first.json()["database"] == "CONNECTED"
        await _drain(queue)

        async def _dead(_session):
            return False

        monkeypatch.setattr("app.api.system._database_is_live", _dead)

        second = await client.get("/system")
        assert second.json()["database"] == "ERROR"

        events = await _drain(queue)
        health_changed = [e for e in events if e.type == EventType.SYSTEM_HEALTH_CHANGED]
        assert len(health_changed) == 1
        changed = health_changed[0].payload["changed"]
        assert changed["database"] == {"from": "CONNECTED", "to": "ERROR"}
        # security also flips off the back of the same forced DB outage —
        # both real changes are reported, nothing unrelated is.
        assert "security" in changed
        assert "desktop" not in changed
        assert "ai" not in changed
    finally:
        await event_bus.unsubscribe(queue)
