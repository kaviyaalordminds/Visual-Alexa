"""Home Assistant tool definitions and executors for iot.ha.*.
Registered into ToolRegistry at startup when HA is configured.
Each tool is a thin wrapper over HomeAssistantClient; all security
constraints (SENSITIVE risk, Policy Engine gate) apply as normal.
"""

from __future__ import annotations

import time
import logging

from veyra_contracts import (
    ErrorCategory,
    ErrorInfo,
    EvidenceTier,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)

from app.services.iot.home_assistant import (
    HomeAssistantClient,
    HomeAssistantError,
    device_name_to_entity_id,
    resolve_domain,
)

logger = logging.getLogger(__name__)

_client = HomeAssistantClient()


class HACallServiceExecutor:
    """Executor for iot.ha.call_service — the single, general-purpose
    Home Assistant service-call tool. The planner populates 'device',
    'action', and optionally 'state'/'value' from the StructuredIntent."""

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        started = time.monotonic()
        device = call.arguments.get("device", "")
        action = call.arguments.get("action", "power")
        state = call.arguments.get("state", "on")
        value = call.arguments.get("value", "")

        domain = resolve_domain(device)
        entity_id = device_name_to_entity_id(device, domain)

        try:
            if action == "set" and value:
                if domain == "climate":
                    await _client.call_service(
                        domain, "set_temperature",
                        entity_id=entity_id,
                        extra={"temperature": _parse_numeric(value)},
                    )
                elif domain == "light":
                    await _client.call_service(
                        domain, "turn_on",
                        entity_id=entity_id,
                        extra={"brightness_pct": _parse_numeric(value)},
                    )
                else:
                    await _client.call_service(
                        domain, "set_value",
                        entity_id=entity_id,
                        extra={"value": value},
                    )
            else:
                service = "turn_on" if str(state).lower() == "on" else "turn_off"
                await _client.call_service(domain, service, entity_id=entity_id)

            return ToolResult(
                call_id=call.call_id,
                status=ToolResultStatus.SUCCESS,
                output={
                    "device": device,
                    "entity_id": entity_id,
                    "action": action,
                    "state": state or value,
                },
                evidence_tier_used=EvidenceTier.NATIVE_API,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
        except HomeAssistantError as exc:
            return ToolResult(
                call_id=call.call_id,
                status=ToolResultStatus.FAILURE,
                error=ErrorInfo.build(
                    ErrorCategory.NETWORK_ERROR, str(exc), call.correlation_id
                ),
                duration_ms=round((time.monotonic() - started) * 1000),
            )


class HAGetStateExecutor:
    """Executor for iot.ha.get_state — reads the current state of a device."""

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        started = time.monotonic()
        entity_id = call.arguments.get("entity_id", "")

        try:
            state_data = await _client.get_state(entity_id)
            return ToolResult(
                call_id=call.call_id,
                status=ToolResultStatus.SUCCESS,
                output={
                    "entity_id": entity_id,
                    "state": state_data.get("state"),
                    "attributes": state_data.get("attributes", {}),
                },
                evidence_tier_used=EvidenceTier.NATIVE_API,
                duration_ms=round((time.monotonic() - started) * 1000),
            )
        except HomeAssistantError as exc:
            return ToolResult(
                call_id=call.call_id,
                status=ToolResultStatus.FAILURE,
                error=ErrorInfo.build(
                    ErrorCategory.NETWORK_ERROR, str(exc), call.correlation_id
                ),
                duration_ms=round((time.monotonic() - started) * 1000),
            )


def _parse_numeric(value: str) -> float | str:
    try:
        return float(str(value).replace("°", "").replace("C", "").replace("F", "").strip())
    except ValueError:
        return value


def build_ha_tools() -> list[tuple[ToolDefinition, object]]:
    """Returns (definition, executor) pairs for all HA tools."""
    call_service_def = ToolDefinition(
        id="iot.ha.call_service",
        name="Home Assistant: Control Device",
        description=(
            "Control a Home Assistant smart-home device: turn lights, AC, fans, "
            "switches on/off; set temperature or brightness."
        ),
        category=ToolCategory.IOT,
        input_schema={
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device name (e.g. 'living room light', 'AC', 'fan')",
                },
                "action": {
                    "type": "string",
                    "enum": ["power", "set"],
                    "description": "Action: 'power' to turn on/off, 'set' to set a value",
                },
                "state": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Power state for 'power' action",
                },
                "value": {
                    "type": "string",
                    "description": "Value to set (temperature in °C, brightness %, etc.)",
                },
            },
            "required": ["device", "action"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "device": {"type": "string"},
                "entity_id": {"type": "string"},
                "action": {"type": "string"},
                "state": {"type": "string"},
            },
        },
        risk_level=RiskLevel.SENSITIVE,
        required_permission="iot.home_assistant.control",
        keywords=["smart home", "iot", "home assistant", "light", "ac", "device", "switch"],
    )

    get_state_def = ToolDefinition(
        id="iot.ha.get_state",
        name="Home Assistant: Get Device State",
        description="Get the current state of a Home Assistant entity by its entity ID.",
        category=ToolCategory.IOT,
        input_schema={
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "HA entity ID, e.g. 'light.living_room'",
                },
            },
            "required": ["entity_id"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "state": {"type": "string"},
                "attributes": {"type": "object"},
            },
        },
        risk_level=RiskLevel.SAFE,
        required_permission="iot.home_assistant.read",
        keywords=["smart home", "iot", "home assistant", "state", "status"],
    )

    return [
        (call_service_def, HACallServiceExecutor()),
        (get_state_def, HAGetStateExecutor()),
    ]
