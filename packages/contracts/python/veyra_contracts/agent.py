"""Phase 4 agent contracts — intent, plan, recovery. Pure data shapes,
no behavior (CLAUDE.md: contracts hold typed shapes; service packages
hold behavior). See docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md §2 for
why these live here rather than in a new package: `IntentInterpreter`/
`TaskPlanner`/`RecoveryManager` are Local-API-only behavior
(`app/services/agent/`), but the shapes they produce are worth a single
shared source of truth the same way `ToolCallRequest`/`ToolResult`
already are.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from veyra_contracts.enums import Confidence, RecoveryStrategy, RiskLevel

IntentStatus = Literal["UNDERSTOOD", "AMBIGUOUS", "MISSING_INFORMATION", "UNSAFE"]


class StructuredIntent(BaseModel):
    """docs/phase-4/INTENT.md — IntentInterpreter's output. Never executes
    anything; a pure classification of a natural-language request."""

    raw_request: str
    goal: str | None = None
    object: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    entities: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.SAFE
    status: IntentStatus = "MISSING_INFORMATION"
    missing_fields: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None


class PlanStep(BaseModel):
    """docs/phase-4/PLANNER.md — one planned tool call. `tool_id` must
    name a tool that exists in the real Tool Registry at plan time
    (enforced by `ToolSelector`, never by the planner assuming a tool
    exists) — see docs/phase-4/TOOL-SELECTION.md."""

    sequence: int = Field(ge=1)
    description: str
    intent: str | None = None
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str | None = None
    risk_level: RiskLevel
    verification_strategy: str | None = None
    confidence: Confidence = Confidence.HIGH


class ExecutionPlan(BaseModel):
    """docs/phase-4/PLANNER.md. `risk_level` is the maximum across all
    steps (never an average — same discipline Phase 3's
    `max_privacy_level` already established for privacy)."""

    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_empty(self) -> bool:
        return not self.steps


class RecoveryDecision(BaseModel):
    """docs/phase-4/RECOVERY.md — RecoveryManager's output. Diagnostic,
    not blind retry: `reason` records what was actually checked."""

    strategy: RecoveryStrategy
    reason: str
    retry_count: int = 0
