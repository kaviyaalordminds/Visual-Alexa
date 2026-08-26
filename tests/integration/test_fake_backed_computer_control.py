"""Exercises application/window/ui/keyboard orchestration — Policy Engine
integration, verification, TARGET_CONTEXT_REQUIRED — against
computer_control.testing's fake backends, since the real Windows ones
cannot run in this environment. See
docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2.
"""

from computer_control.core.models import UIElementInfo


async def _grant(client, tool_id, risk):
    resp = await client.post(
        "/permissions", json={"tool_id": tool_id, "risk_level": risk, "scope": "ALLOW_SESSION"}
    )
    assert resp.status_code == 201


async def test_application_launch_is_verified_against_the_fake_backend(
    client, fake_computer_control
):
    resp = await client.post(
        "/tools/application.launch/invoke",
        json={"arguments": {"application": "fakeapp"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["output"]["status"] == "VERIFIED"
    assert body["output"]["verification"]["passed"] is True


async def test_application_launch_of_unknown_app_is_denied(client, fake_computer_control):
    resp = await client.post(
        "/tools/application.launch/invoke",
        json={"arguments": {"application": "totally-unknown-app"}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "APPLICATION_NOT_FOUND"


async def test_window_focus_minimize_maximize_round_trip(client, fake_computer_control):
    await _grant(client, "window.close", "MODERATE")
    window_backend = fake_computer_control["window"]
    window = window_backend.add_window_for_process(process_id=4242, title="Fake Notepad")

    focus_resp = await client.post(
        "/tools/window.focus/invoke", json={"arguments": {"handle": window.handle}}
    )
    assert focus_resp.json()["output"]["verification"]["passed"] is True

    minimize_resp = await client.post(
        "/tools/window.minimize/invoke", json={"arguments": {"handle": window.handle}}
    )
    assert minimize_resp.json()["output"]["verification"]["passed"] is True

    close_resp = await client.post(
        "/tools/window.close/invoke", json={"arguments": {"handle": window.handle}}
    )
    assert close_resp.json()["output"]["status"] == "VERIFIED"

    # the window is really gone from the fake backend now
    list_resp = await client.post("/tools/window.list/invoke", json={"arguments": {}})
    assert window.handle not in [w["handle"] for w in list_resp.json()["output"]["data"]["windows"]]


async def test_window_action_on_unknown_handle_is_window_not_found(client, fake_computer_control):
    resp = await client.post(
        "/tools/window.focus/invoke", json={"arguments": {"handle": "does-not-exist"}}
    )
    assert resp.json()["error"]["code"] == "WINDOW_NOT_FOUND"


async def test_ui_find_and_click_against_a_seeded_element(client, fake_computer_control):
    await _grant(client, "ui.click", "SENSITIVE")
    ui_backend = fake_computer_control["ui_automation"]
    ui_backend.seed_element(UIElementInfo(automation_id="save-btn", name="Save", enabled=True))

    find_resp = await client.post(
        "/tools/ui.find/invoke",
        json={"arguments": {"selector": {"automation_id": "save-btn"}}},
    )
    assert find_resp.status_code == 200
    assert find_resp.json()["output"]["data"]["element"]["name"] == "Save"

    click_resp = await client.post(
        "/tools/ui.click/invoke",
        json={"arguments": {"selector": {"automation_id": "save-btn"}}},
    )
    assert click_resp.json()["output"]["status"] == "EXECUTED"


async def test_ui_find_missing_element_is_ui_not_found(client, fake_computer_control):
    resp = await client.post(
        "/tools/ui.find/invoke",
        json={
            "arguments": {
                "selector": {"automation_id": "does-not-exist"},
                "timeout_seconds": 0.2,
            }
        },
    )
    assert resp.json()["error"]["code"] == "UI_NOT_FOUND"


async def test_keyboard_type_with_no_target_is_target_context_required(
    client, fake_computer_control
):
    await _grant(client, "keyboard.type", "SENSITIVE")
    resp = await client.post(
        "/tools/keyboard.type/invoke",
        json={"arguments": {"target": {}, "text": "hello"}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "TARGET_CONTEXT_REQUIRED"
    assert body["error"]["user_action_required"] is True


async def test_keyboard_type_with_a_real_target_succeeds(client, fake_computer_control):
    await _grant(client, "keyboard.type", "SENSITIVE")
    resp = await client.post(
        "/tools/keyboard.type/invoke",
        json={"arguments": {"target": {"window_title": "Notepad"}, "text": "Hello VEYRA"}},
    )
    assert resp.json()["output"]["status"] == "EXECUTED"


async def test_mouse_click_with_no_selector_criteria_is_target_context_required(
    client, fake_computer_control
):
    await _grant(client, "mouse.click", "SENSITIVE")
    resp = await client.post("/tools/mouse.click/invoke", json={"arguments": {"selector": {}}})
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "TARGET_CONTEXT_REQUIRED"
