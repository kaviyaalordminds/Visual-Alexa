"""docs/phase-4/TASK-ENGINE.md — hard guardrails. CLAUDE.md: 'no unbounded
loops, ever.'"""

from __future__ import annotations

from app.services.agent.loop_protection import LoopBudgetTracker
from veyra_contracts import TaskBudget


def test_max_steps_exceeded_detected():
    tracker = LoopBudgetTracker(
        budget=TaskBudget(max_steps=2, timeout_seconds=60, max_recovery_attempts=1)
    )
    tracker.record_step()
    tracker.record_step()
    assert tracker.budget_exceeded_reason() is not None


def test_under_budget_is_not_exceeded():
    tracker = LoopBudgetTracker(
        budget=TaskBudget(max_steps=10, timeout_seconds=60, max_recovery_attempts=1)
    )
    tracker.record_step()
    assert tracker.budget_exceeded_reason() is None


def test_timeout_exceeded_detected():
    tracker = LoopBudgetTracker(
        budget=TaskBudget(max_steps=100, timeout_seconds=1, max_recovery_attempts=1)
    )
    tracker._started_at -= 2  # simulate elapsed time without a real sleep
    assert tracker.budget_exceeded_reason() is not None


def test_max_replans_exceeded_detected():
    tracker = LoopBudgetTracker(
        budget=TaskBudget(max_steps=100, timeout_seconds=60, max_recovery_attempts=1, max_replans=1)
    )
    tracker.record_replan()
    tracker.record_replan()
    assert tracker.budget_exceeded_reason() is not None


def test_identical_call_repeated_is_detected_as_a_loop():
    tracker = LoopBudgetTracker(
        budget=TaskBudget(max_steps=100, timeout_seconds=60, max_recovery_attempts=1)
    )
    args = {"path": "/a/b.txt"}
    results = [tracker.record_call_and_check_loop("filesystem.open", args) for _ in range(3)]
    assert results == [False, False, True]


def test_same_tool_different_arguments_is_not_a_loop():
    tracker = LoopBudgetTracker(
        budget=TaskBudget(max_steps=100, timeout_seconds=60, max_recovery_attempts=1)
    )
    for i in range(5):
        detected = tracker.record_call_and_check_loop(
            "filesystem.search", {"directory": f"/root{i}"}
        )
        assert detected is False
