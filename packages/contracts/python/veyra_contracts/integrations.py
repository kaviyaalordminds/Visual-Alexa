"""Integration contracts. docs/architecture/11-INTEGRATIONS.md,
docs/phase-7/INTEGRATION-ARCHITECTURE.md.

Mirrors the already-documented `Integration` interface (§2 of the
architecture doc): `id, auth_method, connect(credentials) ->
ConnectionResult, disconnect(), capabilities, invoke(capability, args) ->
IntegrationResult`. `IntegrationResult` deliberately mirrors `ToolResult`
(same `status`/`error` shape) — an integration capability's outcome is
always turned into an ordinary `ToolResult` by the executor that wraps
it, so keeping the shapes aligned means that mapping is a straight
field copy, not a translation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from veyra_contracts.enums import AuthMethod, IntegrationState, ToolCategory, ToolResultStatus
from veyra_contracts.errors import ErrorInfo


class IntegrationDefinition(BaseModel):
    id: str = Field(description="Stable id, e.g. 'reference'.")
    name: str
    category: ToolCategory
    auth_method: AuthMethod
    required_scopes: list[str] = Field(default_factory=list)
    description: str


class ConnectionResult(BaseModel):
    success: bool
    state: IntegrationState
    reason: str | None = None


class IntegrationResult(BaseModel):
    status: ToolResultStatus
    data: dict[str, Any] | None = None
    error: ErrorInfo | None = None
