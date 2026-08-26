"""Permission contracts. docs/security/02-PERMISSION-MODEL.md"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from veyra_contracts.enums import PermissionDecision, RiskLevel


class PermissionRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    action: str = Field(description="tool_id being requested")
    target: str | None = None
    reason: str
    risk_level: RiskLevel
    affected_resource: str | None = None
    proposed_arguments: dict[str, Any] = Field(default_factory=dict)
    expiration: datetime | None = None
    user_decision: PermissionDecision | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PermissionGrant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    tool_id: str
    target: str | None = Field(
        default=None, description="None = applies to any target for this tool."
    )
    risk_level: RiskLevel
    scope: PermissionDecision
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_valid(self, at: datetime | None = None) -> bool:
        """A grant is valid iff not revoked and not expired. CRITICAL-risk
        grants are never valid for satisfying a check regardless of this
        method — see docs/security/08-SENSITIVE-ACTION-POLICY.md §2 and
        PolicyEngine in services/local-api."""
        now = at or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True
