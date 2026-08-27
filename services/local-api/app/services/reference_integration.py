"""ReferenceIntegration — docs/phase-7/PHASE-7-IMPLEMENTATION-PLAN.md
§3.5, brief §112-113's "one safe reference integration."

Deliberately not a disguised real product: no Gmail/Spotify/WhatsApp
implementation ships here (per the brief's own Stop Condition §176). Its
one capability does no network I/O — it validates a real stored
credential exists, then echoes its input back through the exact same
`ToolResult` shape every other tool uses. What's under test is the
platform mechanics (register, connect with a real stored credential,
execute through the real Policy Engine, audit, health-check, disconnect),
not any particular product's API — and a zero-network reference is
deterministic and safe to run in CI forever, unlike a live call to any
real service.
"""

from __future__ import annotations

from time import monotonic

from veyra_contracts import (
    AuthMethod,
    ErrorCategory,
    ErrorInfo,
    IntegrationDefinition,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)

from app.services.credential_manager import CredentialManager
from app.services.integration_registry import IntegrationBundle

REFERENCE_INTEGRATION_ID = "reference"
REFERENCE_ECHO_TOOL_ID = "reference.echo"

_ECHO_TOOL_DEFINITION = ToolDefinition(
    id=REFERENCE_ECHO_TOOL_ID,
    name="Reference Echo",
    description=(
        "Reference/example integration capability — echoes its input back. "
        "Demonstrates the full integration lifecycle (connect, execute, "
        "health check, disconnect) with zero network dependency. Not a "
        "real product integration."
    ),
    category=ToolCategory.CUSTOM,
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
    output_schema={"type": "object", "properties": {"echo": {"type": "string"}}},
    risk_level=RiskLevel.SAFE,
    required_permission="reference.invoke",
    integration_id=REFERENCE_INTEGRATION_ID,
    keywords=["reference", "demo", "example", "echo"],
)


class ReferenceEchoExecutor:
    """Bound to one specific connection's credential ref at build time
    (`IntegrationRegistry.connect` passes it in) — this is what makes
    disconnecting genuinely revoke the capability rather than merely
    hiding it: even if a stale reference to this executor object
    outlived `unregister` somehow, it would still refuse to run once its
    ref no longer validates."""

    def __init__(self, credential_manager: CredentialManager, credentials_ref: str) -> None:
        self._credential_manager = credential_manager
        self._ref = credentials_ref

    async def execute(self, call: ToolCallRequest) -> ToolResult:
        started = monotonic()
        if not self._credential_manager.validate_credential(self._ref):
            return ToolResult(
                call_id=call.call_id,
                status=ToolResultStatus.FAILURE,
                error=ErrorInfo.build(
                    code=ErrorCategory.NOT_CONNECTED,
                    message="The reference integration is not connected.",
                    correlation_id=call.correlation_id,
                ),
                duration_ms=round((monotonic() - started) * 1000),
            )
        text = call.arguments.get("text", "")
        return ToolResult(
            call_id=call.call_id,
            status=ToolResultStatus.SUCCESS,
            output={"echo": text},
            duration_ms=round((monotonic() - started) * 1000),
        )


def build_reference_integration_bundle(credential_manager: CredentialManager) -> IntegrationBundle:
    return IntegrationBundle(
        definition=IntegrationDefinition(
            id=REFERENCE_INTEGRATION_ID,
            name="Reference Integration",
            category=ToolCategory.CUSTOM,
            auth_method=AuthMethod.API_KEY,
            required_scopes=[],
            description=(
                "A deliberately non-real reference/example integration "
                "demonstrating the full connect/execute/health-check/"
                "disconnect lifecycle with zero network dependency."
            ),
        ),
        tool_definitions=[_ECHO_TOOL_DEFINITION],
        build_executor=lambda _tool_def, ref: ReferenceEchoExecutor(credential_manager, ref),
    )
