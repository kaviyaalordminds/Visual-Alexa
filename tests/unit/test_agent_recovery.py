"""docs/phase-4/RECOVERY.md — diagnostic, bounded recovery decisions."""

from __future__ import annotations

from app.services.agent.recovery import RecoveryManager
from veyra_contracts import ErrorCategory, RecoveryStrategy, TaskBudget

_BUDGET = TaskBudget(max_steps=10, timeout_seconds=60, max_recovery_attempts=2, max_replans=2)


def test_transient_error_retries_within_budget():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.TIMEOUT, retry_count=0, replan_count=0, budget=_BUDGET
    )
    assert decision.strategy == RecoveryStrategy.RETRY
    assert decision.retry_count == 1


def test_transient_error_escalates_to_replan_after_retries_exhausted():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.TIMEOUT, retry_count=2, replan_count=0, budget=_BUDGET
    )
    assert decision.strategy == RecoveryStrategy.REPLAN


def test_transient_error_asks_user_after_replans_exhausted_too():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.TIMEOUT, retry_count=2, replan_count=2, budget=_BUDGET
    )
    assert decision.strategy == RecoveryStrategy.ASK_USER


def test_ui_not_found_regrounds_not_blind_retry():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.UI_NOT_FOUND, retry_count=0, replan_count=0, budget=_BUDGET
    )
    assert decision.strategy == RecoveryStrategy.REGROUND


def test_verification_failed_reobserves():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.VERIFICATION_FAILED, retry_count=0, replan_count=0, budget=_BUDGET
    )
    assert decision.strategy == RecoveryStrategy.REOBSERVE


def test_permanent_error_aborts_immediately_never_retried():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.APPLICATION_NOT_FOUND,
        retry_count=0,
        replan_count=0,
        budget=_BUDGET,
    )
    assert decision.strategy == RecoveryStrategy.ABORT
    assert decision.retry_count == 0


def test_capability_unavailable_never_retried():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.CAPABILITY_UNAVAILABLE,
        retry_count=0,
        replan_count=0,
        budget=_BUDGET,
    )
    assert decision.strategy == RecoveryStrategy.ABORT


def test_unknown_tool_never_retried():
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.UNKNOWN_TOOL, retry_count=0, replan_count=0, budget=_BUDGET
    )
    assert decision.strategy == RecoveryStrategy.ABORT


def test_zero_recovery_attempts_budget_immediately_escalates():
    budget = TaskBudget(max_steps=10, timeout_seconds=60, max_recovery_attempts=0, max_replans=0)
    decision = RecoveryManager().decide(
        error_code=ErrorCategory.TIMEOUT, retry_count=0, replan_count=0, budget=budget
    )
    assert decision.strategy == RecoveryStrategy.ASK_USER
