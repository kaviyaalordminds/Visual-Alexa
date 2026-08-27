"""docs/phase-6/AVATAR-ARCHITECTURE.md — the real `voice.ui_state.changed`
publishing VoiceConversationManager now does at each genuine transition
point. Subscribes to the real event_bus, exactly like
test_voice_events.py, so these are end-to-end against the actual manager,
never a mock of it.
"""

from __future__ import annotations

import os
from uuid import uuid4

from app.api.deps import get_or_create_local_user
from app.core.event_bus import event_bus
from app.models.task import Task as TaskRow
from app.services.agent.orchestrator import request_pause
from app.services.agent.register import get_orchestrator
from app.services.voice.register import get_voice_manager
from veyra_contracts import EventType, TaskBudget, TaskState


async def _drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def _ui_states(events):
    return [e.payload["agent_state"] for e in events if e.type == EventType.VOICE_UI_STATE_CHANGED]


async def test_ui_state_sequence_for_a_completed_task(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    queue = await event_bus.subscribe()
    try:
        manager = get_voice_manager()
        session = await manager.start_session(db_session)
        await manager.submit_utterance(db_session, session.id, "search for invoice")
        await manager.finish_response(db_session, session.id)

        events = await _drain(queue)
        # LISTENING (session start) -> THINKING (processing) -> SPEAKING
        # (response) -> IDLE (finish_response) — every state this pipeline
        # can genuinely reach for a single ordinary turn, in real order.
        assert _ui_states(events) == ["LISTENING", "THINKING", "SPEAKING", "IDLE"]
    finally:
        await event_bus.unsubscribe(queue)


async def test_speaking_state_carries_a_real_viseme_timeline(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    queue = await event_bus.subscribe()
    try:
        manager = get_voice_manager()
        session = await manager.start_session(db_session)
        await manager.submit_utterance(db_session, session.id, "search for invoice")

        events = await _drain(queue)
        speaking = [
            e
            for e in events
            if e.type == EventType.VOICE_UI_STATE_CHANGED and e.payload["agent_state"] == "SPEAKING"
        ]
        assert len(speaking) == 1
        visemes = speaking[0].payload["visemes"]
        assert visemes  # a real, non-empty spoken response always yields frames
        assert all("shape" in f and "start_ms" in f and "duration_ms" in f for f in visemes)
        # outcome reflects the real terminal TaskState (COMPLETED -> SUCCESS)
        assert speaking[0].payload["outcome"] == "SUCCESS"
    finally:
        await event_bus.unsubscribe(queue)


async def test_speaking_outcome_reflects_capability_unavailable_as_error(db_session, fs_sandbox):
    queue = await event_bus.subscribe()
    try:
        manager = get_voice_manager()
        session = await manager.start_session(db_session)
        await manager.submit_utterance(db_session, session.id, "delete all files in Downloads")

        events = await _drain(queue)
        speaking = [
            e
            for e in events
            if e.type == EventType.VOICE_UI_STATE_CHANGED and e.payload["agent_state"] == "SPEAKING"
        ]
        assert len(speaking) == 1
        assert speaking[0].payload["outcome"] == "ERROR"
    finally:
        await event_bus.unsubscribe(queue)


async def test_stop_speaking_returns_ui_state_to_listening_with_no_visemes(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    manager = get_voice_manager()
    session = await manager.start_session(db_session)
    await manager.submit_utterance(db_session, session.id, "search for invoice")

    queue = await event_bus.subscribe()
    try:
        await manager.submit_utterance(db_session, session.id, "Stop.")
        events = await _drain(queue)
        ui_events = [e for e in events if e.type == EventType.VOICE_UI_STATE_CHANGED]
        assert len(ui_events) == 1
        assert ui_events[0].payload["agent_state"] == "LISTENING"
        assert "visemes" not in ui_events[0].payload
    finally:
        await event_bus.unsubscribe(queue)


async def test_resume_after_pause_reports_paused_then_success_outcome(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    user = await get_or_create_local_user(db_session)
    budget = TaskBudget(max_steps=10, timeout_seconds=60, max_recovery_attempts=2)
    task = TaskRow(
        user_id=user.id,
        description="search for invoice",
        state=TaskState.RECEIVED,
        max_steps=budget.max_steps,
        timeout_seconds=budget.timeout_seconds,
        max_recovery_attempts=budget.max_recovery_attempts,
        max_replans=budget.max_replans,
        correlation_id=str(uuid4()),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    request_pause(task.id)
    await get_orchestrator().run(db_session, task)
    await db_session.refresh(task)
    assert task.state == TaskState.PAUSED

    manager = get_voice_manager()
    session = await manager.start_session(db_session)
    session.active_task_id = task.id

    queue = await event_bus.subscribe()
    try:
        await manager.submit_utterance(db_session, session.id, "continue")
        events = await _drain(queue)
        speaking = [
            e
            for e in events
            if e.type == EventType.VOICE_UI_STATE_CHANGED and e.payload["agent_state"] == "SPEAKING"
        ]
        assert len(speaking) == 1
        assert speaking[0].payload["outcome"] == "SUCCESS"
    finally:
        await event_bus.unsubscribe(queue)
