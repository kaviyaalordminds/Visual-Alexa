"""Tool contracts. docs/architecture/04-TOOL-ARCHITECTURE.md"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from veyra_contracts.enums import (
    ConfirmationPolicy,
    EvidenceTier,
    RiskLevel,
    ToolCategory,
    ToolResultStatus,
)
from veyra_contracts.errors import ErrorInfo


class ToolDefinition(BaseModel):
    """Every tool the system can ever call must be registered as one of
    these. CLAUDE.md: 'Every tool must be registered via
    ToolRegistry.register() with a risk_level and required_permission;
    unregistered tools cannot execute.'
    """

    id: str = Field(description="Stable, namespaced id, e.g. 'system.get_status'")
    name: str
    description: str
    category: ToolCategory
    input_schema: dict[str, Any] = Field(
        description="JSON Schema describing valid arguments."
    )
    output_schema: dict[str, Any] = Field(
        description="JSON Schema describing the tool's output shape."
    )
    risk_level: RiskLevel
    required_permission: str = Field(
        description="Permission scope key checked by the Policy Engine."
    )
    confirmation_policy: ConfirmationPolicy = ConfirmationPolicy.NEVER
    timeout_seconds: int = Field(default=30, gt=0)
    cancellable: bool = True
    verification_strategy: str = Field(
        default="none",
        description="Human-readable description of how ToolVerifier "
        "confirms this tool's expected postcondition.",
    )
    audit_metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallRequest(BaseModel):
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_id: str
    target: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )


class ToolResult(BaseModel):
    call_id: str
    status: ToolResultStatus
    output: dict[str, Any] | None = None
    error: ErrorInfo | None = None
    evidence_tier_used: EvidenceTier | None = None
    duration_ms: int = Field(ge=0)
