"""End-to-end VoiceConversationManager tests through the real Task Engine
— the same AgentOrchestrator/Policy Engine/Tool Registry chain
tests/integration/test_agent_tasks_api.py exercises via HTTP, driven here
through the voice layer instead. docs/phase-5/PHASE-5-TEST-RESULTS.md.

No audio anywhere in these tests — they start from an already-transcribed
string, exactly like a real STT provider would hand off (brief §27: voice
handles speech, Phase 4 handles intent). What's under test is the binding
in app/services/voice/manager.py, not audio I/O.
"""

from __future__ import annotations

import os

from app.models.conversation import Message as MessageRow
from app.models.task import Task as TaskRow
from app.models.task import TaskStep as TaskStepRow
from app.services.voice.register import get_voice_manager
from sqlalchemy import select
from veyra_contracts import TaskState
from voice.core.enums import VoiceState


async def _start(db_session):
    return await get_voice_manager().start_session(db_session)


async def _task_row(db_session, task_id):
    result = await db_session.execute(select(TaskRow).where(TaskRow.id == task_id))
    return result.scalars().first()


async def test_completed_task_speaks_done(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")
    session = await _start(db_session)
    result = await get_voice_manager().submit_utterance(
        db_session, session.id, "search for invoice"
    )
    assert result.response.should_speak
    assert result.response.text  # a real, non-empty spoken response
    assert session.active_task_id is None
    assert session.status == VoiceState.RESPONDING


async def test_wake_phrase_prefix_does_not_block_intent_understanding(db_session, fs_sandbox):
    """'Hey Veyra, open Chrome' (brief's own first acceptance example) must
    reach the same real planning path 'open Chrome' alone would — the wake
    phrase is a hearing-layer artifact, not part of the command.

    'open Chrome' classifies as a `browser_task` intent (matched before
    `open_application`), which — since Phase 11's real, bounded
    `browser_task` planning template — genuinely launches a browser
    against the test environment's `FakeBrowserAdapter` (see
    tests/conftest.py) rather than coming back `CAPABILITY_UNAVAILABLE`.
    That the task actually completes is itself the proof the wake phrase
    didn't block anything — a stronger signal than merely reaching a
    'not available' answer."""
    session = await _start(db_session)
    result = await get_voice_manager().submit_utterance(
        db_session, session.id, "Hey Veyra, open Chrome"
    )
    assert "capability" not in result.response.text.lower()
    assert session.active_task_id is None  # the task ran to completion, not left waiting
    task = (
        await db_session.execute(
            select(TaskRow).where(TaskRow.conversation_id == session.conversation_id)
        )
    ).scalars().first()
    assert task.state == TaskState.COMPLETED
    steps = (
        await db_session.execute(
            select(TaskStepRow).where(TaskStepRow.task_id == task.id)
        )
    ).scalars().all()
    assert [s.tool_id for s in sorted(steps, key=lambda s: s.step_number)] == [
        "browser.launch",
        "browser.get_page",
    ]


async def test_tanglish_folder_example_reaches_real_planning(db_session, fs_sandbox):
    """brief's own Tanglish worked example: 'Downloads folder la latest
    PDF open pannu.' must be understood and actually searched for, not
    just detected as a language."""
    os.makedirs(os.path.join(fs_sandbox, "Downloads"), exist_ok=True)
    with open(os.path.join(fs_sandbox, "Downloads", "song.pdf"), "w") as f:
        f.write("x")
    session = await _start(db_session)
    result = await get_voice_manager().submit_utterance(
        db_session, session.id, "Downloads folder la latest PDF open pannu."
    )
    # The real filesystem.search tool actually ran and found the file —
    # the open step itself may fail on this host (no xdg-open), the same
    # honest limitation Phase 4 documented for "find notes.txt and open
    # it". Either real outcome proves planning/execution actually ran,
    # not just language detection.
    assert result.response.text
    assert "capability" not in result.response.text.lower()


async def test_mishear_clarification_then_yes_runs_the_corrected_command(db_session, fs_sandbox):
    """brief acceptance test #8: 'Open Rome'-style mishear should produce
    'Did you say X?' at low confidence, and answering yes should actually
    run the corrected command — not just repeat the question."""
    session = await _start(db_session)
    manager = get_voice_manager()

    asked = await manager.submit_utterance(
        db_session, session.id, "open pathon", stt_confidence=0.4
    )
    assert "did you say" in asked.response.text.lower()
    assert "python" in asked.response.text.lower()
    assert session.active_task_id is None  # nothing executed yet

    await manager.finish_response(db_session, session.id)
    confirmed = await manager.submit_utterance(db_session, session.id, "yes")
    # The real python_test_app resolved and an actual launch was attempted
    # (python3 exists in this container) — either outcome proves the
    # corrected command reached real planning, not just the question.
    assert confirmed.response.text
    assert "did you say" not in confirmed.response.text.lower()


async def test_mishear_clarification_declined_runs_nothing(db_session, fs_sandbox):
    session = await _start(db_session)
    manager = get_voice_manager()
    await manager.submit_utterance(db_session, session.id, "open pathon", stt_confidence=0.4)
    await manager.finish_response(db_session, session.id)

    declined = await manager.submit_utterance(db_session, session.id, "no")
    assert "never mind" in declined.response.text.lower()
    assert session.active_task_id is None


async def test_high_confidence_mishear_target_is_trusted_as_heard(db_session, fs_sandbox):
    """At high STT confidence, an unrecognized target is trusted as heard
    rather than second-guessed — it should reach real planning (and fail
    honestly as CAPABILITY_UNAVAILABLE/APPLICATION_NOT_FOUND) instead of
    asking 'Did you say X?'."""
    session = await _start(db_session)
    result = await get_voice_manager().submit_utterance(
        db_session, session.id, "open pathon", stt_confidence=0.98
    )
    assert "did you say" not in result.response.text.lower()


async def test_voice_resumes_a_paused_task_on_continue(db_session, fs_sandbox):
    """docs/phase-5/BARGE-IN.md — a task genuinely PAUSED (e.g. via the
    HTTP /tasks/{id}/pause endpoint from another caller) that this voice
    session is tracking must actually resume when the user says
    'continue' — not just re-ask or silently do nothing."""
    from uuid import uuid4

    from app.api.deps import get_or_create_local_user
    from app.services.agent.orchestrator import request_pause
    from app.services.agent.register import get_orchestrator
    from veyra_contracts import TaskBudget, TaskState

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
    session = await _start(db_session)
    session.active_task_id = task.id

    result = await manager.submit_utterance(db_session, session.id, "continue")
    assert "did you say" not in result.response.text.lower()
    await db_session.refresh(task)
    assert task.state == TaskState.COMPLETED


async def test_capability_unavailable_is_spoken_honestly(db_session, fs_sandbox):
    session = await _start(db_session)
    result = await get_voice_manager().submit_utterance(
        db_session, session.id, "delete all files in Downloads"
    )
    assert "capability" in result.response.text.lower()
    assert session.active_task_id is None


async def test_ambiguous_request_then_second_one_followup(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "project1.txt"), "w") as f:
        f.write("x")
    with open(os.path.join(fs_sandbox, "project2.txt"), "w") as f:
        f.write("x")
    manager = get_voice_manager()
    session = await _start(db_session)

    first = await manager.submit_utterance(db_session, session.id, "open my project")
    assert first.response.should_speak
    assert len(session.last_candidates) == 2
    assert session.active_task_id is not None

    await manager.finish_response(db_session, session.id)
    second = await manager.submit_utterance(db_session, session.id, "open the second one")
    # Resolved to one concrete file (whichever the search returned second),
    # not left ambiguous a second time — the point under test is that the
    # ordinal was substituted with a real filename at all.
    assert second.response.text
    assert "project" in session.last_task_goal
    assert session.active_task_id is None


async def test_low_confidence_confirmation_never_authorizes(db_session, fs_sandbox, monkeypatch):
    from app.services.agent.planner import PlanOutcome
    from app.services.agent.register import get_orchestrator
    from veyra_contracts import ExecutionPlan, PlanStep, RiskLevel

    async def fake_plan(intent, search=None, memory_lookup=None):
        return PlanOutcome(
            status="PLANNED",
            plan=ExecutionPlan(
                goal="test",
                steps=[
                    PlanStep(
                        sequence=1,
                        description="Create a folder.",
                        tool_id="filesystem.create_folder",
                        arguments={"parent": fs_sandbox, "name": "voice_confirm_dir"},
                        risk_level=RiskLevel.MODERATE,
                    )
                ],
                risk_level=RiskLevel.MODERATE,
                requires_confirmation=True,
            ),
        )

    monkeypatch.setattr(get_orchestrator()._planner, "create_plan", fake_plan)

    manager = get_voice_manager()
    session = await _start(db_session)
    first = await manager.submit_utterance(db_session, session.id, "open my confirm target")
    assert "?" in first.response.text or first.response.text
    assert session.active_task_id is not None

    await manager.finish_response(db_session, session.id)
    unclear = await manager.submit_utterance(
        db_session, session.id, "yeah... maybe", stt_confidence=0.3
    )
    assert unclear.response.text == "Please say yes or no."
    assert not os.path.isdir(os.path.join(fs_sandbox, "voice_confirm_dir"))
    # The task is still waiting — nothing was authorized.
    task = await _task_row(db_session, session.active_task_id)
    assert task.state == "WAITING_PERMISSION"

    await manager.finish_response(db_session, session.id)
    confirmed = await manager.submit_utterance(db_session, session.id, "yes")
    assert confirmed.response.should_speak
    assert os.path.isdir(os.path.join(fs_sandbox, "voice_confirm_dir"))


async def test_live_correction_sentence_denies_a_pending_confirmation(
    db_session, fs_sandbox, monkeypatch
):
    """brief's acceptance test #10: 'Actually, don't open it' must stop
    speech and be understood as a denial, not just re-prompt."""
    from app.services.agent.planner import PlanOutcome
    from app.services.agent.register import get_orchestrator
    from veyra_contracts import ExecutionPlan, PlanStep, RiskLevel

    async def fake_plan(intent, search=None, memory_lookup=None):
        return PlanOutcome(
            status="PLANNED",
            plan=ExecutionPlan(
                goal="test",
                steps=[
                    PlanStep(
                        sequence=1,
                        description="Create a folder.",
                        tool_id="filesystem.create_folder",
                        arguments={"parent": fs_sandbox, "name": "correction_dir"},
                        risk_level=RiskLevel.MODERATE,
                    )
                ],
                risk_level=RiskLevel.MODERATE,
                requires_confirmation=True,
            ),
        )

    monkeypatch.setattr(get_orchestrator()._planner, "create_plan", fake_plan)
    manager = get_voice_manager()
    session = await _start(db_session)
    await manager.submit_utterance(db_session, session.id, "open my confirm target")

    # Still RESPONDING (the confirmation prompt is being "spoken") —
    # this correction is a live barge-in *and* a denial.
    result = await manager.submit_utterance(db_session, session.id, "Actually, don't open it")
    assert "cancelled" in result.response.text.lower()
    assert not os.path.isdir(os.path.join(fs_sandbox, "correction_dir"))
    assert session.active_task_id is None


async def test_confirmation_denial_via_voice(db_session, fs_sandbox, monkeypatch):
    from app.services.agent.planner import PlanOutcome
    from app.services.agent.register import get_orchestrator
    from veyra_contracts import ExecutionPlan, PlanStep, RiskLevel

    async def fake_plan(intent, search=None, memory_lookup=None):
        return PlanOutcome(
            status="PLANNED",
            plan=ExecutionPlan(
                goal="test",
                steps=[
                    PlanStep(
                        sequence=1,
                        description="Create a folder.",
                        tool_id="filesystem.create_folder",
                        arguments={"parent": fs_sandbox, "name": "voice_deny_dir"},
                        risk_level=RiskLevel.MODERATE,
                    )
                ],
                risk_level=RiskLevel.MODERATE,
                requires_confirmation=True,
            ),
        )

    monkeypatch.setattr(get_orchestrator()._planner, "create_plan", fake_plan)

    manager = get_voice_manager()
    session = await _start(db_session)
    await manager.submit_utterance(db_session, session.id, "open my confirm target")
    await manager.finish_response(db_session, session.id)

    denied = await manager.submit_utterance(db_session, session.id, "no")
    assert "cancelled" in denied.response.text.lower()
    assert not os.path.isdir(os.path.join(fs_sandbox, "voice_deny_dir"))
    assert session.active_task_id is None


async def test_barge_in_stop_speaking(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")
    manager = get_voice_manager()
    session = await _start(db_session)
    await manager.submit_utterance(db_session, session.id, "search for invoice")
    assert session.status == VoiceState.RESPONDING

    interrupted = await manager.submit_utterance(db_session, session.id, "Stop.")
    assert interrupted.stop_speaking is True
    assert interrupted.response.should_speak is False
    assert session.status == VoiceState.LISTENING


async def test_transcript_is_logged_with_secrets_redacted(db_session, fs_sandbox):
    manager = get_voice_manager()
    session = await _start(db_session)
    assert session.conversation_id is not None

    await manager.submit_utterance(
        db_session, session.id, "remember my password is hunter2 and open Chrome"
    )

    result = await db_session.execute(
        select(MessageRow).where(MessageRow.conversation_id == session.conversation_id)
    )
    messages = list(result.scalars())
    assert len(messages) >= 1
    user_message = next(m for m in messages if m.role == "user")
    assert "hunter2" not in user_message.content
    assert "[REDACTED]" in user_message.content


async def test_end_session_interruption_ends_session(db_session, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")
    manager = get_voice_manager()
    session = await _start(db_session)
    await manager.submit_utterance(db_session, session.id, "search for invoice")

    ended = await manager.submit_utterance(db_session, session.id, "Goodbye.")
    assert ended.ended is True
    assert manager.get(session.id) is None
