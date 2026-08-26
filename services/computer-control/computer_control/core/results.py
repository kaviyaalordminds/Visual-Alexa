"""Structured action result model. docs/phase-2 §22.

'Never return success when verification failed' is enforced by
construction here: ActionResult.success is derived from `status`, not set
independently, so a caller cannot accidentally set success=True with a
FAILED status.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator
from veyra_contracts import ErrorInfo, EvidenceTier


class ActionStatus(StrEnum):
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"


_SUCCESS_STATUSES = frozenset({ActionStatus.EXECUTED, ActionStatus.VERIFIED})


class VerificationOutcome(BaseModel):
    passed: bool
    method: str
    detail: str | None = None


class ActionResult(BaseModel):
    status: ActionStatus
    tool: str
    target: str | None = None
    execution_time_ms: int = Field(ge=0)
    verification: VerificationOutcome | None = None
    error: ErrorInfo | None = None
    data: dict[str, Any] | None = None
    # docs/architecture/05-COMPUTER-CONTROL.md §1 — which evidence tier
    # actually grounded this action, making the evidence hierarchy
    # auditable rather than aspirational. None for tools the hierarchy
    # doesn't apply to (e.g. screen capture — it produces evidence, it
    # doesn't consume a UI-grounding tier).
    evidence_tier: EvidenceTier | None = None

    @property
    def success(self) -> bool:
        return self.status in _SUCCESS_STATUSES

    @model_validator(mode="after")
    def _verified_requires_a_passing_verification(self) -> ActionResult:
        if self.status is ActionStatus.VERIFIED and not (
            self.verification is not None and self.verification.passed
        ):
            raise ValueError(
                "ActionStatus.VERIFIED requires a VerificationOutcome with passed=True — "
                "docs/phase-2 §21/§22: never claim success merely because a launch "
                "command returned without error."
            )
        return self
