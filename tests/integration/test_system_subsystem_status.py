"""GET /system — subsystem activation (docs/subsystem-activation/
SUBSYSTEM-ACTIVATION-REPORT.md): ai/voice/vision/computer_control/iot are
now derived from real checks, not static settings flags. These tests
prove the exact real-world outcome this sandbox produces (mostly
NOT CONFIGURED/DISABLED, honestly) and that a real event (an AI check
result being recorded, a device permission being granted) genuinely
changes the reported state.
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.agent.llm_provider import LLMResult
from app.services.subsystem_health import record_ai_check_result, reset_ai_check_cache


async def test_defaults_are_honest_not_configured_or_disabled(client):
    """No AI/voice/vision configured, computer_control.enabled defaults to
    True in the test fixture (see conftest.py) but this sandbox is not
    Windows — the real check must report DISABLED, never a fake CONNECTED."""
    resp = await client.get("/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai"] == "NOT CONFIGURED"
    assert body["voice"] == "NOT CONFIGURED"
    assert body["computer_control"] == "DISABLED"
    assert "requires Windows" in body["details"]["computer_control"]
    assert body["iot"] == "NOT CONNECTED"
    assert "details" in body
    assert body["details"]["ai"]  # a real, non-empty reason string


async def test_ai_reports_degraded_once_configured_but_not_yet_tested(client, monkeypatch):
    reset_ai_check_cache()
    fake_settings = Settings(
        ai_provider="openai-compatible",
        ai_model="m",
        ai_api_key="k",
        ai_base_url="https://api.example.com/v1",
    )
    monkeypatch.setattr("app.api.system.get_settings", lambda: fake_settings)

    resp = await client.get("/system")
    body = resp.json()
    assert body["ai"] == "DEGRADED"
    assert "ai_health_check" in body["details"]["ai"]
    reset_ai_check_cache()


async def test_ai_reports_connected_after_a_real_successful_check_is_recorded(client, monkeypatch):
    reset_ai_check_cache()
    fake_settings = Settings(
        ai_provider="openai-compatible",
        ai_model="m",
        ai_api_key="k",
        ai_base_url="https://api.example.com/v1",
    )
    monkeypatch.setattr("app.api.system.get_settings", lambda: fake_settings)
    record_ai_check_result(LLMResult(available=True, content="reachable"))

    resp = await client.get("/system")
    body = resp.json()
    assert body["ai"] == "CONNECTED"
    reset_ai_check_cache()


async def test_iot_reports_connected_once_a_device_has_an_active_permission(client):
    from app.services.device_pairing import device_pairing_service

    resp_before = await client.get("/system")
    assert resp_before.json()["iot"] == "NOT CONNECTED"

    device_pairing_service._permission_cache[("device-x", "power")] = None
    try:
        resp_after = await client.get("/system")
        assert resp_after.json()["iot"] == "CONNECTED"
    finally:
        device_pairing_service.reset_permission_cache()
