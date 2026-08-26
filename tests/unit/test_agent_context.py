"""docs/phase-4/CONTEXT-MANAGEMENT.md, docs/phase-4/TASK-MEMORY.md."""

from __future__ import annotations

from app.services.agent.context import ContextManager, StepRecord, TaskContext


def test_summarize_bounds_recent_step_history():
    context = TaskContext(task_id="t1", user_goal="open notepad")
    for i in range(10):
        context.record_step(StepRecord(sequence=i, tool_id="x", status="SUCCESS", summary="s"))
    summary = ContextManager().summarize_for_planning(context)
    assert len(summary["recent_steps"]) < 10


def test_summarize_preserves_unresolved_errors():
    context = TaskContext(task_id="t1", user_goal="open notepad")
    context.record_error("step 1 failed: TIMEOUT")
    summary = ContextManager().summarize_for_planning(context)
    assert "step 1 failed: TIMEOUT" in summary["unresolved_errors"]


def test_summarize_preserves_retry_and_replan_counts():
    context = TaskContext(task_id="t1", user_goal="x", retry_count=2, replan_count=1)
    summary = ContextManager().summarize_for_planning(context)
    assert summary["retry_count"] == 2
    assert summary["replan_count"] == 1
