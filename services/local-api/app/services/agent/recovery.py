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
    {
        ErrorCategory.VERIFICATION_FAILED,
        ErrorCategory.STATE_MISMATCH,
        # Phase 8 (docs/phase-8/ERROR-RECOVERY.md §86) — the DOM changed
        # under an in-flight action; re-observing before retrying is the
        # same fix as a STATE_MISMATCH, never a blind identical retry.
        ErrorCategory.PAGE_CHANGED,
    }
)
# Resource contention — retrying the identical action fails identically
# (the resource is still busy for the same reason), but unlike
# _PERMANENT_CATEGORIES this isn't unrecoverable: it resolves once
# something frees the resource (e.g. the user closes a browser session
# that's pinning BrowserManager's max_sessions cap). That's a decision
# only the user can make, so this skips straight to ASK_USER with a clear,
# actionable reason rather than either burning the retry budget on a
# retry that cannot succeed or falling through to the generic
# "not a recognized recoverable category" ABORT.
_RESOURCE_CONTENTION_CATEGORIES = frozenset({ErrorCategory.RESOURCE_BUSY})

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
        # Phase 7 — retrying with the same invalid/missing credential or
        # disconnected integration never succeeds; the fix is a user
        # action (reconnect), not spending the retry budget.
        ErrorCategory.AUTH_ERROR,
        ErrorCategory.NOT_CONNECTED,
        # Phase 8 (docs/phase-8/CAPTCHA-HANDLING.md, docs/phase-8/
        # PROMPT-INJECTION-DEFENSE.md) — every one of these needs a human
        # decision (complete the CAPTCHA/OTP themselves, confirm a
        # purchase, decide about a blocked download/URL/injection
        # attempt), never an automatic retry. Fails the task with a clear
        # reason rather than spending the recovery budget on something
        # retrying can never fix.
        ErrorCategory.CAPTCHA_DETECTED,
        ErrorCategory.OTP_REQUIRED,
        ErrorCategory.PAYMENT_CONFIRMATION_REQUIRED,
        ErrorCategory.UNSAFE_URL,
        ErrorCategory.PROMPT_INJECTION_BLOCKED,
        ErrorCategory.DOWNLOAD_BLOCKED,
        ErrorCategory.EXTENSION_AUTH_FAILED,
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

        if error_code in _RESOURCE_CONTENTION_CATEGORIES:
            return RecoveryDecision(
                strategy=RecoveryStrategy.ASK_USER,
                reason=f"'{error_code.value}' — retrying won't help while the resource is "
                "still busy; free it up (e.g. close an existing browser session) or tell me "
                "how to proceed.",
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
