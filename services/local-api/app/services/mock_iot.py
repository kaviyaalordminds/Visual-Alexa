"""MockACDevice tools — docs/phase-7/IOT-ARCHITECTURE.md, brief §166.

"Do NOT connect a real AC/fan/TV yet. Create a mock device provider."
These two tools validate the device-control architecture (pairing,
DevicePermission grant/revoke, honest failure with nothing paired) for
real, without ever touching a real device or scanning a real network.

Deliberately `RiskLevel.SAFE` (so the generic Policy Engine step always
passes through immediately) — the real gate under test here is the
device-specific `DevicePermission` layer
(`DevicePairingService.is_permission_valid`), checked inside the
executor, not a second, overlapping generic `PermissionGrant`. A real
smart-home integration in a future phase would likely want both layers;
this mock's whole purpose is to prove the device layer works in
isolation.
"""

from __future__ import annotations

from time import monotonic

from veyra_contracts import (
    ErrorCategory,
    ErrorInfo,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)

from app.services.device_pairing import DevicePairingService
from app.services.tool_registry import ToolExecutor

MOCK_AC_SET_POWER_TOOL_ID = "iot.mock_ac.set_power"
MOCK_AC_SET_TEMPERATURE_TOOL_ID = "iot.mock_ac.set_temperature"

# In-memory only — a real adapter would forward these to the actual
# device instead; this dict exists so the mock has any observable state
# at all to assert against in tests.
_mock_ac_state: dict[str, dict[str, object]] = {}


def get_mock_ac_state(device_id: str) -> dict[str, object]:
    return dict(_mock_ac_state.get(device_id, {}))


def reset_mock_ac_state() -> None:
    """Test-isolation helper — `_mock_ac_state` is process-global like
    every other registry here (see tool_registry's own precedent)."""
    _mock_ac_state.clear()


def _permission_denied(call: ToolCallRequest, capability_key: str) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        status=ToolResultStatus.FAILURE,
        error=ErrorInfo.build(
            code=ErrorCategory.PERMISSION_DENIED,
            message=f"No valid device permission for '{capability_key}' on this device.",
            correlation_id=call.correlation_id,
            user_action_required=True,
        ),
        duration_ms=0,
    )


def _missing_target(call: ToolCallRequest) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        status=ToolResultStatus.FAILURE,
        error=ErrorInfo.build(
            code=ErrorCategory.VALIDATION_ERROR,
            message="A device id (target) is required.",
            correlation_id=call.correlation_id,
        ),
        duration_ms=0,
    )


def _validation_error(call: ToolCallRequest, message: str) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        status=ToolResultStatus.FAILURE,
        error=ErrorInfo.build(
            code=ErrorCategory.VALIDATION_ERROR, message=message, correlation_id=call.correlation_id
        ),
        duration_ms=0,
    )


class MockACSetPowerExecutor:
    def __init__(self, pairing_service: DevicePairingService) -> None:
        self._pairing_service = pairing_service

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        started = monotonic()
        device_id = call.target
        if not device_id:
            return _missing_target(call)
        if not self._pairing_service.is_permission_valid(device_id, "power"):
            return _permission_denied(call, "power")
        power = call.arguments.get("power")
        # A real bug this phase's own verification found: `bool(...)`
        # silently coerces *any* truthy value — including the string
        # "false" (Python's classic gotcha) — into True. Malicious or
        # merely malformed arguments must fail validation, never be
        # guessed at.
        if not isinstance(power, bool):
            return _validation_error(
                call, f"'power' must be a real boolean, not {type(power).__name__!r}."
            )
        _mock_ac_state.setdefault(device_id, {})["power"] = power
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output={"device_id": device_id, "power": power},
            duration_ms=round((monotonic() - started) * 1000),
        )


class MockACSetTemperatureExecutor:
    def __init__(self, pairing_service: DevicePairingService) -> None:
        self._pairing_service = pairing_service

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        started = monotonic()
        device_id = call.target
        if not device_id:
            return _missing_target(call)
        if not self._pairing_service.is_permission_valid(device_id, "temperature"):
            return _permission_denied(call, "temperature")
        celsius = call.arguments.get("celsius")
        if not isinstance(celsius, (int, float)) or isinstance(celsius, bool):
            return _validation_error(
                call, f"'celsius' must be a real number, not {type(celsius).__name__!r}."
            )
        # A real, unglamorous but genuine safety bound — an MODERATE/SAFE
        # mock device is still a place a malformed or adversarial value
        # (e.g. 1e30) should never reach un-clamped, the same discipline
        # Phase 2 already applies to its own tool arguments.
        if not -50 <= celsius <= 50:
            return _validation_error(call, "'celsius' must be between -50 and 50.")
        _mock_ac_state.setdefault(device_id, {})["celsius"] = celsius
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output={"device_id": device_id, "celsius": celsius},
            duration_ms=round((monotonic() - started) * 1000),
        )


def build_mock_iot_tools(
    pairing_service: DevicePairingService,
) -> list[tuple[ToolDefinition, ToolExecutor]]:
    set_power = ToolDefinition(
        id=MOCK_AC_SET_POWER_TOOL_ID,
        name="Mock AC: Set Power",
        description=(
            "Turn a paired mock air conditioner on or off. Requires a real, "
            "granted DevicePermission for the 'power' capability on the "
            "target device — no real AC is ever contacted."
        ),
        category=ToolCategory.IOT,
        input_schema={
            "type": "object",
            "properties": {"power": {"type": "boolean"}},
            "required": ["power"],
        },
        output_schema={
            "type": "object",
            "properties": {"device_id": {"type": "string"}, "power": {"type": "boolean"}},
        },
        risk_level=RiskLevel.SAFE,
        required_permission="iot.mock_ac.control",
        keywords=["ac", "air conditioner", "power", "smart home", "iot"],
    )
    set_temperature = ToolDefinition(
        id=MOCK_AC_SET_TEMPERATURE_TOOL_ID,
        name="Mock AC: Set Temperature",
        description=(
            "Set a paired mock air conditioner's target temperature. "
            "Requires a real, granted DevicePermission for the "
            "'temperature' capability on the target device."
        ),
        category=ToolCategory.IOT,
        input_schema={
            "type": "object",
            "properties": {"celsius": {"type": "number"}},
            "required": ["celsius"],
        },
        output_schema={
            "type": "object",
            "properties": {"device_id": {"type": "string"}, "celsius": {"type": "number"}},
        },
        risk_level=RiskLevel.SAFE,
        required_permission="iot.mock_ac.control",
        keywords=["ac", "air conditioner", "temperature", "smart home", "iot"],
    )
    return [
        (set_power, MockACSetPowerExecutor(pairing_service)),
        (set_temperature, MockACSetTemperatureExecutor(pairing_service)),
    ]
