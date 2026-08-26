"""docs/phase-2 §22 — 'Never return success when verification failed.'
Enforced structurally: ActionStatus.VERIFIED cannot be constructed without
a passing VerificationOutcome.
"""

import pytest
from computer_control.core.results import ActionResult, ActionStatus, VerificationOutcome
from pydantic import ValidationError


def test_verified_requires_a_passing_verification_outcome():
    with pytest.raises(ValidationError):
        ActionResult(status=ActionStatus.VERIFIED, tool="test.tool", execution_time_ms=1)


def test_verified_with_failed_verification_is_rejected():
    with pytest.raises(ValidationError):
        ActionResult(
            status=ActionStatus.VERIFIED,
            tool="test.tool",
            execution_time_ms=1,
            verification=VerificationOutcome(passed=False, method="x"),
        )


def test_verified_with_passing_verification_is_accepted():
    result = ActionResult(
        status=ActionStatus.VERIFIED,
        tool="test.tool",
        execution_time_ms=1,
        verification=VerificationOutcome(passed=True, method="x"),
    )
    assert result.success is True


def test_executed_does_not_require_verification():
    result = ActionResult(status=ActionStatus.EXECUTED, tool="test.tool", execution_time_ms=1)
    assert result.success is True


@pytest.mark.parametrize(
    "status",
    [ActionStatus.FAILED, ActionStatus.DENIED, ActionStatus.UNKNOWN, ActionStatus.PARTIAL],
)
def test_non_success_statuses_report_success_false(status):
    result = ActionResult(status=status, tool="test.tool", execution_time_ms=1)
    assert result.success is False
