"""system.ai_health_check / system.voice_health_check — the user-
triggerable diagnostic actions docs/subsystem-activation/AI-STATUS.md and
VOICE-STATUS.md call for ("Test Voice", "AI HEALTH CHECK"). Registered
the same way `bootstrap.py` registers `system.get_status` — same
ToolRegistry -> PolicyEngine -> Executor -> AuditLog chokepoint every
other tool uses, not a second execution path.

`system.ai_health_check` is the only place in this build that ever makes
a real network call to a configured AI provider outside an explicit user
action — never on an automatic timer, never from `/system`'s own passive
poll (see app/services/agent/providers.py's docstring).
"""

from __future__ import annotations

import time

from veyra_contracts import (
    ConfirmationPolicy,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)

from app.core.config import get_settings
from app.services.agent.llm_provider import NotConfiguredLLMProvider
from app.services.agent.providers import build_llm_provider
from app.services.subsystem_health import compute_voice_status, record_ai_check_result
from app.services.tool_registry import ToolRegistry

AI_HEALTH_CHECK_TOOL = ToolDefinition(
    id="system.ai_health_check",
    name="AI Health Check",
    description="Read-only: verifies whether the configured AI provider is reachable. "
    "A cheap reachability probe only — never sends a billable inference request.",
    category=ToolCategory.SYSTEM,
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema={"type": "object"},
    risk_level=RiskLevel.SAFE,
    required_permission="system.read_status",
    confirmation_policy=ConfirmationPolicy.NEVER,
    verification_strategy="none — read-only, nothing to verify a postcondition against.",
)


class AIHealthCheckExecutor:
    async def execute(self, call: ToolCallRequest) -> ToolResult:
        start = time.monotonic()
        settings = get_settings()
        provider = build_llm_provider(settings)
        if isinstance(provider, NotConfiguredLLMProvider):
            output = {
                "configured": False,
                "reachable": False,
                "reason": "No AI provider configured.",
            }
        else:
            result = await provider.health_check()
            record_ai_check_result(result)
            output = {
                "configured": True,
                "reachable": result.available,
                "reason": result.reason or "Reachable.",
            }
        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output=output,
            duration_ms=duration_ms,
        )


VOICE_HEALTH_CHECK_TOOL = ToolDefinition(
    id="system.voice_health_check",
    name="Voice Health Check",
    description="Read-only: reports which STT/TTS/wake-word providers are configured "
    "and whether a real audio implementation is wired in to this build.",
    category=ToolCategory.SYSTEM,
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    output_schema={"type": "object"},
    risk_level=RiskLevel.SAFE,
    required_permission="system.read_status",
    confirmation_policy=ConfirmationPolicy.NEVER,
    verification_strategy="none — read-only, nothing to verify a postcondition against.",
)


class VoiceHealthCheckExecutor:
    async def execute(self, call: ToolCallRequest) -> ToolResult:
        start = time.monotonic()
        health = compute_voice_status(get_settings())
        duration_ms = int((time.monotonic() - start) * 1000)
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output={"status": health.status, "reason": health.reason},
            duration_ms=duration_ms,
        )


def register_subsystem_diagnostic_tools(registry: ToolRegistry) -> None:
    registry.register(AI_HEALTH_CHECK_TOOL, AIHealthCheckExecutor())
    registry.register(VOICE_HEALTH_CHECK_TOOL, VoiceHealthCheckExecutor())
