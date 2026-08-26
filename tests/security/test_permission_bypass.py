"""docs/research/03-COMPETITOR-WEAKNESSES.md item 9 (over-permissioned
agents) — a tool call must never bypass the Policy Engine, regardless of
how the caller frames the request.
"""

import pytest
from app.services.tool_execution import UnknownToolError, execute_tool_call
from app.services.tool_registry import tool_registry
from veyra_contracts import ToolCallRequest


async def test_unregistered_tool_id_cannot_be_invoked(db_session):
    call = ToolCallRequest(tool_id="filesystem.delete_everything", correlation_id="corr-1")
    with pytest.raises(UnknownToolError):
        await execute_tool_call(db_session, tool_registry, call=call, user_id="u1")


async def test_a_prompt_injected_style_reason_does_not_change_the_outcome(client):
    """The Policy Engine never trusts the caller's stated justification —
    docs/security/07-PROMPT-INJECTION.md §3.2. Whatever the client sends as
    'arguments', the SAFE-tier tool still only returns its own fixed,
    read-only output — model-influenced arguments cannot widen what the
    tool actually does.
    """
    resp = await client.post(
        "/tools/system.get_status/invoke",
        json={"arguments": {"ignore_previous_instructions": True, "risk_level": "SAFE"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Output is exactly the read-only settings dump, not influenced by the
    # attacker-controlled "arguments" payload.
    assert set(body["output"].keys()) == {
        "microphone.enabled",
        "screen_observation.enabled",
        "external_devices.enabled",
        "remote_access.enabled",
        "ai.mode",
        "ai.configured",
        "voice.configured",
        "vision.configured",
        "computer_control.enabled",
        "security.active",
    }
