"""Phase 12 — the genuinely-new EventType categories PHASE_12_AUDIT.md
found absent, each published at a real, pre-existing decision point (no
new decision logic added just to have something to publish). All events
are subscribed to on the real `event_bus`, exercised through the real
HTTP API, exactly like the existing avatar-UI-state tests
(test_browser_avatar_ui_state.py) this file mirrors.
"""

from __future__ import annotations

import asyncio

from app.api.tasks import _background_tasks
from app.core.event_bus import event_bus
from app.services.browser.adapter import RawElement
from app.services.browser.manager import browser_manager
from app.services.browser.testing import FakePage
from veyra_contracts import EventType


async def _drain(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


async def _drain_background_tasks(timeout_seconds: float = 5.0) -> None:
    """Mirrors test_agent_tasks_api.py's own helper — a `/run`/`/confirm`
    background task still in flight when a test ends can hold a real
    SQLite write lock past this test's own event loop, racing the next
    test's fixture (`DROP TABLE`). Draining here closes that race."""
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while _background_tasks and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.01)


def _types(events):
    return [e.type for e in events]


async def _pair_ac_to_control(client, capability_keys=("power",)):
    resp = await client.post(
        "/devices/pair", json={"name": "Living Room AC", "type": "AC", "protocol": "LOCAL_HTTP"}
    )
    device_id = resp.json()["id"]
    await client.post(f"/devices/{device_id}/identify")
    await client.post(f"/devices/{device_id}/authenticate", json={"secret": "s"})
    await client.post(f"/devices/{device_id}/authorize")
    return device_id


async def test_register_capabilities_publishes_iot_device_connected(client):
    queue = await event_bus.subscribe()
    try:
        device_id = await _pair_ac_to_control(client)
        resp = await client.post(
            f"/devices/{device_id}/register-capabilities", json={"capability_keys": ["power"]}
        )
        assert resp.status_code == 200
        events = await _drain(queue)
        connected = [e for e in events if e.type == EventType.IOT_DEVICE_CONNECTED]
        assert len(connected) == 1
        assert connected[0].payload["device_id"] == device_id
    finally:
        await event_bus.unsubscribe(queue)


async def test_revoke_permission_publishes_iot_device_disconnected(client):
    device_id = await _pair_ac_to_control(client)
    await client.post(
        f"/devices/{device_id}/register-capabilities", json={"capability_keys": ["power"]}
    )
    await client.post(f"/devices/{device_id}/permissions/grant", json={"capability_key": "power"})

    queue = await event_bus.subscribe()
    try:
        resp = await client.post(
            f"/devices/{device_id}/permissions/revoke", json={"capability_key": "power"}
        )
        assert resp.status_code == 200
        events = await _drain(queue)
        disconnected = [e for e in events if e.type == EventType.IOT_DEVICE_DISCONNECTED]
        assert len(disconnected) == 1
        assert disconnected[0].payload["device_id"] == device_id
    finally:
        await event_bus.unsubscribe(queue)


async def test_iot_tool_call_publishes_command_started_and_completed(client):
    device_id = await _pair_ac_to_control(client)
    await client.post(
        f"/devices/{device_id}/register-capabilities", json={"capability_keys": ["power"]}
    )
    await client.post(f"/devices/{device_id}/permissions/grant", json={"capability_key": "power"})

    queue = await event_bus.subscribe()
    try:
        resp = await client.post(
            "/tools/iot.mock_ac.set_power/invoke",
            json={"target": device_id, "arguments": {"power": True}},
        )
        assert resp.status_code == 200
        events = await _drain(queue)
        assert EventType.IOT_COMMAND_STARTED in _types(events)
        assert EventType.IOT_COMMAND_COMPLETED in _types(events)
    finally:
        await event_bus.unsubscribe(queue)


async def test_non_iot_tool_call_never_publishes_iot_command_events(client, fs_sandbox):
    """A non-IoT tool (filesystem.search) must never trigger the IoT
    observability events — the gate is real category matching, not 'any
    tool call at all.'"""
    queue = await event_bus.subscribe()
    try:
        await client.post(
            "/tools/filesystem.search/invoke",
            json={"arguments": {"directory": fs_sandbox}},
        )
        events = await _drain(queue)
        assert EventType.IOT_COMMAND_STARTED not in _types(events)
        assert EventType.IOT_COMMAND_COMPLETED not in _types(events)
    finally:
        await event_bus.unsubscribe(queue)


async def test_every_tool_call_publishes_audit_record_created(client, fs_sandbox):
    queue = await event_bus.subscribe()
    try:
        await client.post(
            "/tools/filesystem.search/invoke",
            json={"arguments": {"directory": fs_sandbox}},
        )
        events = await _drain(queue)
        audit_events = [e for e in events if e.type == EventType.AUDIT_RECORD_CREATED]
        assert len(audit_events) == 1
        assert audit_events[0].payload["tool_id"] == "filesystem.search"
    finally:
        await event_bus.unsubscribe(queue)


async def test_captcha_stop_publishes_security_blocked(client):
    await client.post("/tools/browser.launch/invoke", json={})
    session = browser_manager.registry.get(browser_manager.active_session_id)
    session.adapter.add_page(
        "https://x/",
        FakePage(
            text="Please verify you are human by completing the CAPTCHA below.",
            elements=[
                RawElement(
                    element_ref="1",
                    role="button",
                    tag="button",
                    text="Continue",
                    aria_label=None,
                    placeholder=None,
                    name=None,
                    value=None,
                    visible=True,
                    enabled=True,
                    bounding_box={"x": 0, "y": 0, "width": 20, "height": 10},
                )
            ],
        ),
    )
    await client.post("/tools/browser.navigate/invoke", json={"arguments": {"url": "https://x/"}})
    await client.post(
        "/permissions",
        json={"tool_id": "browser.click", "risk_level": "MODERATE", "scope": "ALLOW_SESSION"},
    )
    queue = await event_bus.subscribe()
    try:
        await client.post("/tools/browser.click/invoke", json={"arguments": {"query": "Continue"}})
        events = await _drain(queue)
        blocked = [e for e in events if e.type == EventType.SECURITY_BLOCKED]
        assert len(blocked) == 1
        assert blocked[0].payload["reason"] == "CAPTCHA"
    finally:
        await event_bus.unsubscribe(queue)


async def test_unsafe_url_publishes_security_blocked(client):
    await client.post("/tools/browser.launch/invoke", json={})
    queue = await event_bus.subscribe()
    try:
        resp = await client.post(
            "/tools/browser.navigate/invoke",
            json={"arguments": {"url": "javascript:alert(1)"}},
        )
        assert resp.json()["status"] == "FAILURE"
        events = await _drain(queue)
        blocked = [e for e in events if e.type == EventType.SECURITY_BLOCKED]
        assert len(blocked) == 1
        assert blocked[0].payload["reason"] == "UNSAFE_URL"
    finally:
        await event_bus.unsubscribe(queue)


async def test_connect_publishes_integration_connected(client):
    queue = await event_bus.subscribe()
    try:
        resp = await client.post(
            "/integrations/reference/connect", json={"secret": "test-api-key"}
        )
        assert resp.status_code == 200
        events = await _drain(queue)
        connected = [e for e in events if e.type == EventType.INTEGRATION_CONNECTED]
        assert len(connected) == 1
        assert connected[0].payload["integration_id"] == "reference"
    finally:
        await event_bus.unsubscribe(queue)


async def test_disconnect_publishes_integration_disconnected(client):
    await client.post("/integrations/reference/connect", json={"secret": "test-api-key"})
    queue = await event_bus.subscribe()
    try:
        resp = await client.post("/integrations/reference/disconnect")
        assert resp.status_code == 200
        events = await _drain(queue)
        disconnected = [e for e in events if e.type == EventType.INTEGRATION_DISCONNECTED]
        assert len(disconnected) == 1
    finally:
        await event_bus.unsubscribe(queue)


async def test_memory_create_update_delete_publish_memory_updated(client):
    queue = await event_bus.subscribe()
    try:
        create_resp = await client.post(
            "/memory",
            json={
                "category": "SEMANTIC",
                "key": "browser",
                "content": {"value": "Firefox"},
                "source": "user_explicit",
            },
        )
        memory_id = create_resp.json()["id"]
        await client.patch(f"/memory/{memory_id}", json={"content": {"value": "Chrome"}})
        await client.delete(f"/memory/{memory_id}")
        events = await _drain(queue)
        updates = [e for e in events if e.type == EventType.MEMORY_UPDATED]
        assert [e.payload["action"] for e in updates] == ["created", "updated", "deleted"]
    finally:
        await event_bus.unsubscribe(queue)


async def test_bulk_clear_memory_removes_all_records_and_publishes_event(client):
    await client.post(
        "/memory",
        json={"category": "SEMANTIC", "content": {"a": 1}, "source": "user_explicit"},
    )
    await client.post(
        "/memory",
        json={"category": "USER_PREFERENCE", "content": {"b": 2}, "source": "user_explicit"},
    )
    queue = await event_bus.subscribe()
    try:
        resp = await client.delete("/memory")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 2
        assert (await client.get("/memory")).json() == []
        events = await _drain(queue)
        cleared = [e for e in events if e.type == EventType.MEMORY_UPDATED]
        assert len(cleared) == 1
        assert cleared[0].payload == {"action": "cleared", "category": None}
    finally:
        await event_bus.unsubscribe(queue)


async def test_bulk_clear_memory_scoped_to_one_category(client):
    await client.post(
        "/memory",
        json={"category": "SEMANTIC", "content": {"a": 1}, "source": "user_explicit"},
    )
    await client.post(
        "/memory",
        json={"category": "USER_PREFERENCE", "content": {"b": 2}, "source": "user_explicit"},
    )
    resp = await client.delete("/memory", params={"category": "SEMANTIC"})
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1
    remaining = (await client.get("/memory")).json()
    assert len(remaining) == 1
    assert remaining[0]["category"] == "USER_PREFERENCE"


async def test_confirmation_approval_publishes_permission_approved(
    client, fs_sandbox, monkeypatch
):
    from app.services.agent.planner import PlanOutcome
    from app.services.agent.register import get_orchestrator
    from veyra_contracts import ExecutionPlan, PlanStep, RiskLevel

    async def fake_plan(intent, search=None, memory_lookup=None):
        plan = ExecutionPlan(
            goal="test_confirmation",
            steps=[
                PlanStep(
                    sequence=1,
                    description="Create a folder.",
                    tool_id="filesystem.create_folder",
                    arguments={"parent": fs_sandbox, "name": "phase12_event_test_dir"},
                    risk_level=RiskLevel.MODERATE,
                )
            ],
            risk_level=RiskLevel.MODERATE,
            requires_confirmation=True,
        )
        return PlanOutcome(status="PLANNED", plan=plan)

    monkeypatch.setattr(get_orchestrator()._planner, "create_plan", fake_plan)

    create = await client.post(
        "/tasks",
        json={
            "description": "open my confirm-event-target",
            "budget": {
                "max_steps": 10,
                "timeout_seconds": 30,
                "max_recovery_attempts": 1,
                "max_replans": 1,
            },
        },
    )
    task_id = create.json()["id"]
    await client.post(f"/tasks/{task_id}/run")


    for _ in range(200):
        state = (await client.get(f"/tasks/{task_id}")).json()["state"]
        if state == "WAITING_PERMISSION":
            break
        await asyncio.sleep(0.02)

    queue = await event_bus.subscribe()
    try:
        resp = await client.post(f"/tasks/{task_id}/confirm", json={"decision": "ALLOW_ONCE"})
        assert resp.status_code == 200
        events = await _drain(queue)
        approved = [e for e in events if e.type == EventType.PERMISSION_APPROVED]
        assert len(approved) == 1
        assert approved[0].payload["tool_id"] == "filesystem.create_folder"
    finally:
        await event_bus.unsubscribe(queue)


async def test_confirmation_denial_publishes_permission_denied(client, fs_sandbox, monkeypatch):
    from app.services.agent.planner import PlanOutcome
    from app.services.agent.register import get_orchestrator
    from veyra_contracts import ExecutionPlan, PlanStep, RiskLevel

    async def fake_plan(intent, search=None, memory_lookup=None):
        plan = ExecutionPlan(
            goal="test_confirmation",
            steps=[
                PlanStep(
                    sequence=1,
                    description="Create a folder.",
                    tool_id="filesystem.create_folder",
                    arguments={"parent": fs_sandbox, "name": "phase12_event_test_dir2"},
                    risk_level=RiskLevel.MODERATE,
                )
            ],
            risk_level=RiskLevel.MODERATE,
            requires_confirmation=True,
        )
        return PlanOutcome(status="PLANNED", plan=plan)

    monkeypatch.setattr(get_orchestrator()._planner, "create_plan", fake_plan)

    create = await client.post(
        "/tasks",
        json={
            "description": "open my confirm-deny-event-target",
            "budget": {
                "max_steps": 10,
                "timeout_seconds": 30,
                "max_recovery_attempts": 1,
                "max_replans": 1,
            },
        },
    )
    task_id = create.json()["id"]
    await client.post(f"/tasks/{task_id}/run")

    for _ in range(200):
        state = (await client.get(f"/tasks/{task_id}")).json()["state"]
        if state == "WAITING_PERMISSION":
            break
        await asyncio.sleep(0.02)
    await _drain_background_tasks()

    queue = await event_bus.subscribe()
    try:
        resp = await client.post(f"/tasks/{task_id}/confirm", json={"decision": "DENY"})
        assert resp.status_code == 200
        events = await _drain(queue)
        denied = [e for e in events if e.type == EventType.PERMISSION_DENIED]
        assert len(denied) == 1
    finally:
        await event_bus.unsubscribe(queue)
    await _drain_background_tasks()


async def test_step_level_permission_pause_publishes_permission_requested(
    client, fs_sandbox, monkeypatch
):
    from app.services.agent.orchestrator import AgentOrchestrator, ToolResultStatus
    from veyra_contracts import ErrorCategory, ErrorInfo, ToolResult

    async def denies_with_confirmation(self, session, task, tool_id, arguments, **_ignored):
        return ToolResult(
            call_id="test-call",
            status=ToolResultStatus.FAILURE,
            error=ErrorInfo(
                code=ErrorCategory.PERMISSION_DENIED,
                message="needs confirmation",
                retryable=False,
                user_action_required=True,
                correlation_id=task.correlation_id,
            ),
            duration_ms=1,
        )

    monkeypatch.setattr(AgentOrchestrator, "_call_tool", denies_with_confirmation)

    queue = await event_bus.subscribe()
    try:
        create = await client.post(
            "/tasks",
            json={
                "description": "search for invoice",
                "budget": {
                    "max_steps": 10,
                    "timeout_seconds": 30,
                    "max_recovery_attempts": 1,
                    "max_replans": 1,
                },
            },
        )
        task_id = create.json()["id"]
        await client.post(f"/tasks/{task_id}/run")

        for _ in range(200):
            state = (await client.get(f"/tasks/{task_id}")).json()["state"]
            if state == "WAITING_PERMISSION":
                break
            await asyncio.sleep(0.02)
        await _drain_background_tasks()

        events = await _drain(queue)
        requested = [e for e in events if e.type == EventType.PERMISSION_REQUESTED]
        assert len(requested) == 1
        assert requested[0].payload["tool_id"] == "filesystem.search"
    finally:
        await event_bus.unsubscribe(queue)
