"""RecoveryManager — diagnoses a failed step and picks a bounded recovery
strategy. docs/phase-4/RECOVERY.md.

Diagnostic, not blind retry (docs/architecture/14-TASK-LIFECYCLE.md §3,
carried into Phase 4): the decision is a pure function of the error code
and how many attempts have already been spent, reusing
`veyra_contracts.errors.RETRYABLE_CATEGORIES` (Phase 1) as the base
retryability signal rather than a second, parallel classification.
"""

from __future__ import annotations

from veyra_contracts import ErrorCategory, RecoveryDecision, RecoveryStrategy, TaskBudget
from veyra_contracts.errors import RETRYABLE_CATEGORIES

# docs/phase-4 §27 — errors where re-observing/re-grounding the target is
# the more precise recovery than a blind identical retry.
_REGROUND_CATEGORIES = frozenset({ErrorCategory.UI_NOT_FOUND, ErrorCategory.AMBIGUOUS_TARGET})
_REOBSERVE_CATEGORIES = frozenset(
    {ErrorCategory.VERIFICATION_FAILED, ErrorCategory.STATE_MISMATCH}
)
# Permanent — no amount of retrying changes the outcome; escalate straight
# to the user or abort, never spend the retry budget on these.
_PERMANENT_CATEGORIES = frozenset(
    {
        ErrorCategory.APPLICATION_NOT_FOUND,
        ErrorCategory.APPLICATION_LAUNCH_FAILED,
        ErrorCategory.FILE_NOT_FOUND,
        ErrorCategory.PLATFORM_NOT_SUPPORTED,
        ErrorCategory.TOOL_DISABLED,
        ErrorCategory.UNKNOWN_TOOL,
        ErrorCategory.CAPABILITY_UNAVAILABLE,
        ErrorCategory.PATH_NOT_ALLOWED,
        ErrorCategory.PATH_PROTECTED,
        ErrorCategory.VALIDATION_ERROR,
        ErrorCategory.INVALID_PLAN,
    }
)


class RecoveryManager:
    def decide(
        self,
        *,
        error_code: ErrorCategory,
        retry_count: int,
        replan_count: int,
        budget: TaskBudget,
    ) -> RecoveryDecision:
        if error_code in _PERMANENT_CATEGORIES:
            return RecoveryDecision(
                strategy=RecoveryStrategy.ABORT,
                reason=f"'{error_code.value}' is not recoverable by retrying.",
                retry_count=retry_count,
            )

        retries_exhausted = retry_count >= budget.max_recovery_attempts
        if error_code in _REGROUND_CATEGORIES:
            if not retries_exhausted:
                return RecoveryDecision(
                    strategy=RecoveryStrategy.REGROUND,
                    reason=f"'{error_code.value}' — re-observing and re-grounding the target "
                    f"(attempt {retry_count + 1}/{budget.max_recovery_attempts}).",
                    retry_count=retry_count + 1,
                )
            return RecoveryDecision(
                strategy=RecoveryStrategy.ASK_USER,
                reason=f"Could not ground the target after {retry_count} attempts.",
                retry_count=retry_count,
            )

        if error_code in _REOBSERVE_CATEGORIES:
            if not retries_exhausted:
                return RecoveryDecision(
                    strategy=RecoveryStrategy.REOBSERVE,
                    reason=f"'{error_code.value}' — the observed state did not match what was "
                    f"expected; re-observing (attempt {retry_count + 1}/"
                    f"{budget.max_recovery_attempts}).",
                    retry_count=retry_count + 1,
                )
            if replan_count < budget.max_replans:
                return RecoveryDecision(
                    strategy=RecoveryStrategy.REPLAN,
                    reason="Repeated verification failures — replanning with fresh context.",
                    retry_count=retry_count,
                )
            return RecoveryDecision(
                strategy=RecoveryStrategy.ASK_USER,
                reason="Verification kept failing after retrying and replanning.",
                retry_count=retry_count,
            )

        if error_code in RETRYABLE_CATEGORIES:
            if not retries_exhausted:
                return RecoveryDecision(
                    strategy=RecoveryStrategy.RETRY,
                    reason=f"'{error_code.value}' is transient — retrying "
                    f"(attempt {retry_count + 1}/{budget.max_recovery_attempts}).",
                    retry_count=retry_count + 1,
                )
            if replan_count < budget.max_replans:
                return RecoveryDecision(
                    strategy=RecoveryStrategy.REPLAN,
                    reason=f"'{error_code.value}' persisted after {retry_count} retries.",
                    retry_count=retry_count,
                )
            return RecoveryDecision(
                strategy=RecoveryStrategy.ASK_USER,
                reason=f"'{error_code.value}' persisted after retrying and replanning.",
                retry_count=retry_count,
            )

        return RecoveryDecision(
            strategy=RecoveryStrategy.ABORT,
            reason=f"'{error_code.value}' is not a recognized recoverable category.",
            retry_count=retry_count,
        )
