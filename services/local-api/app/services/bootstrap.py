"""Registers Phase 1's example SAFE-tier tool. docs/architecture/04-TOOL-ARCHITECTURE.md
§5: 'the registry ships with example SAFE-tier stub definitions ... so the
registry -> policy -> executor -> verify -> audit path is exercised
end-to-end by tests without performing any real OS action.'
"""

from __future__ import annotations

import time

from sqlalchemy import select
from veyra_contracts import (
    ConfirmationPolicy,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)

from app.db.session import SessionLocal
from app.models.setting import SystemSetting
from app.services.tool_registry import ToolRegistry

SYSTEM_STATUS_TOOL = ToolDefinition(
    id="system.get_status",
    name="Get System Status",
    description="Read-only: returns current VEYRA component status "
    "(desktop, local API, database, AI, voice, vision, computer control, "
    "IoT, security).",
    category=ToolCategory.SYSTEM,
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema={"type": "object"},
    risk_level=RiskLevel.SAFE,
    required_permission="system.read_status",
    confirmation_policy=ConfirmationPolicy.NEVER,
    verification_strategy="none — read-only, nothing to verify a postcondition against.",
)


class SystemStatusExecutor:
    """Opens its own short-lived session per call rather than capturing a
    request-scoped session at registration time, since the registry is a
    process-lifetime singleton (docs/architecture/04-TOOL-ARCHITECTURE.md)."""

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        start = time.monotonic()
        async with SessionLocal() as session:
            result = await session.execute(select(SystemSetting))
            output = {row.key: row.value for row in result.scalars()}
        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output=output,
            duration_ms=duration_ms,
        )


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(SYSTEM_STATUS_TOOL, SystemStatusExecutor())
