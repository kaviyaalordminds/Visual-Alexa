"""Standardized error model. Product brief §27."""

from __future__ import annotations

from pydantic import BaseModel, Field

from veyra_contracts.enums import ErrorCategory

# Error categories considered safe to retry automatically (bounded by
# TaskBudget.max_recovery_attempts — see docs/architecture/14-TASK-LIFECYCLE.md).
RETRYABLE_CATEGORIES: frozenset[ErrorCategory] = frozenset(
    {
        ErrorCategory.NETWORK_ERROR,
        ErrorCategory.TIMEOUT,
        ErrorCategory.DEVICE_UNAVAILABLE,
        ErrorCategory.TOOL_FAILURE,
        # Phase 2: transient while a window/element is still appearing —
        # exactly why wait_for_element polling exists
        # (docs/phase-2/WINDOWS-UI-AUTOMATION.md). Bounded by
        # TaskBudget.max_recovery_attempts like every other retryable
        # category, never an unbounded loop.
        ErrorCategory.WINDOW_NOT_FOUND,
        ErrorCategory.UI_NOT_FOUND,
        ErrorCategory.UNKNOWN_WINDOWS_ERROR,
    }
)


class ErrorInfo(BaseModel):
    code: ErrorCategory
    message: str
    retryable: bool = Field(
        default=False,
        description="Whether the Task Runtime may attempt an automatic "
        "retry, bounded by TaskBudget.max_recovery_attempts.",
    )
    user_action_required: bool = Field(
        default=False,
        description="Whether resolving this error requires a decision only "
        "the user can make (e.g. ambiguity, missing permission).",
    )
    recovery_strategy: str | None = Field(
        default=None,
        description="Human-readable description of what RECOVERING should "
        "attempt, if anything.",
    )
    correlation_id: str

    @classmethod
    def build(
        cls,
        code: ErrorCategory,
        message: str,
        correlation_id: str,
        recovery_strategy: str | None = None,
        user_action_required: bool = False,
    ) -> ErrorInfo:
        return cls(
            code=code,
            message=message,
            retryable=code in RETRYABLE_CATEGORIES,
            user_action_required=user_action_required,
            recovery_strategy=recovery_strategy,
            correlation_id=correlation_id,
        )
