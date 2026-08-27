"""voice.* events actually publish through the real event_bus.
docs/phase-5/VOICE-EVENTS.md. Only events genuinely triggerable from a
text-only voice turn (no real audio hardware in this environment) are
covered here — `voice.wake_detected` and `voice.transcript.partial` still
have no real trigger (no real wake-word detector or streaming STT) and
are not expected. `voice.ui_state.changed` *is* now real as of Phase 6
(docs/phase-6/AVATAR-ARCHITECTURE.md) — see test_avatar_ui_state.py for
its own dedicated coverage of the payload shape."""

from __future__ import annotations

import os

from app.core.event_bus import event_bus
from app.services.voice.register import get_voice_manager
from veyra_contracts import EventType


async def _drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


async def test_full_turn_publishes_the_expected_event_sequence(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    queue = await event_bus.subscribe()
    try:
        manager = get_voice_manager()
        session = await manager.start_session(db_session)
        await manager.submit_utterance(db_session, session.id, "search for invoice")
        await manager.finish_response(db_session, session.id)

        types = [e.type for e in await _drain(queue)]
        assert EventType.VOICE_LISTENING_STARTED in types
        assert EventType.VOICE_LISTENING_STOPPED in types
        assert EventType.VOICE_LANGUAGE_DETECTED in types
        assert EventType.VOICE_TRANSCRIPT_FINAL in types
        assert EventType.VOICE_INTENT_RECEIVED in types
        assert EventType.VOICE_RESPONSE_STARTED in types
        assert EventType.VOICE_RESPONSE_FINISHED in types
        # No real wake-word/streaming-STT/avatar in this phase — these
        # must never be fabricated (docs/phase-5/VOICE-EVENTS.md §2).
        assert EventType.VOICE_UI_STATE_CHANGED in types
        assert EventType.VOICE_WAKE_DETECTED not in types
        assert EventType.VOICE_TRANSCRIPT_PARTIAL not in types
    finally:
        await event_bus.unsubscribe(queue)


async def test_barge_in_publishes_interrupted_event(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    manager = get_voice_manager()
    session = await manager.start_session(db_session)
    await manager.submit_utterance(db_session, session.id, "search for invoice")

    queue = await event_bus.subscribe()
    try:
        await manager.submit_utterance(db_session, session.id, "Stop.")
        types = [e.type for e in await _drain(queue)]
        assert EventType.VOICE_INTERRUPTED in types
    finally:
        await event_bus.unsubscribe(queue)


async def test_transcript_event_payload_is_redacted(db_session, fs_sandbox):
    queue = await event_bus.subscribe()
    try:
        manager = get_voice_manager()
        session = await manager.start_session(db_session)
        await manager.submit_utterance(
            db_session, session.id, "my password is hunter2 open chrome"
        )
        events = await _drain(queue)
        transcript_events = [e for e in events if e.type == EventType.VOICE_TRANSCRIPT_FINAL]
        assert transcript_events
        assert "hunter2" not in transcript_events[0].payload["text"]
    finally:
        await event_bus.unsubscribe(queue)
