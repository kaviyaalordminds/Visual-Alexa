"""Real, per-subsystem status computation. docs/subsystem-activation/
SUBSYSTEM-ACTIVATION-REPORT.md — the absolute rule under test throughout:
never CONNECTED merely because config exists; only when a real check
actually passed (or, honestly, NOT CONFIGURED/DEGRADED/DISABLED/NOT
CONNECTED otherwise).
"""

from __future__ import annotations

from app.core.config import Settings
from app.services.agent.llm_provider import LLMResult
from app.services.browser.manager import BrowserManager
from app.services.browser.testing import FakeBrowserAdapter
from app.services.device_pairing import DevicePairingService
from app.services.subsystem_health import (
    VoiceComponentStatus,
    compute_ai_status,
    compute_browser_status,
    compute_computer_control_status,
    compute_iot_status,
    compute_vision_status,
    compute_voice_status,
    record_ai_check_result,
    record_voice_stt_status,
    record_voice_tts_status,
    record_voice_wake_word_status,
    reset_ai_check_cache,
    reset_voice_provider_status,
)
from computer_control.core.capabilities import PlatformCapabilities


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def _capabilities(*, is_windows: bool) -> PlatformCapabilities:
    return PlatformCapabilities(
        platform="win32" if is_windows else "linux",
        is_windows=is_windows,
        supports_application_control=is_windows,
        supports_window_management=is_windows,
        supports_ui_automation=is_windows,
        supports_keyboard_mouse=is_windows,
        supports_process_listing=True,
        supports_screen_capture=True,
    )


class TestAIStatus:
    def setup_method(self):
        reset_ai_check_cache()

    def teardown_method(self):
        reset_ai_check_cache()

    def test_not_configured_by_default(self):
        health = compute_ai_status(_settings())
        assert health.status == "NOT CONFIGURED"
        assert "missing" in health.reason

    def test_partial_config_is_still_not_configured(self):
        health = compute_ai_status(_settings(ai_provider="x", ai_model="m"))
        assert health.status == "NOT CONFIGURED"
        assert "API key" in health.reason
        assert "base URL" in health.reason

    def test_fully_configured_but_never_tested_is_degraded_not_connected(self):
        health = compute_ai_status(
            _settings(ai_provider="x", ai_model="m", ai_api_key="k", ai_base_url="https://x")
        )
        assert health.status == "DEGRADED"
        assert "ai_health_check" in health.reason

    def test_after_a_successful_check_reports_connected(self):
        record_ai_check_result(LLMResult(available=True, content="reachable"))
        health = compute_ai_status(
            _settings(ai_provider="x", ai_model="m", ai_api_key="k", ai_base_url="https://x")
        )
        assert health.status == "CONNECTED"

    def test_after_a_failed_check_reports_error_with_the_real_reason(self):
        record_ai_check_result(LLMResult(available=False, reason="auth rejected"))
        health = compute_ai_status(
            _settings(ai_provider="x", ai_model="m", ai_api_key="k", ai_base_url="https://x")
        )
        assert health.status == "ERROR"
        assert health.reason == "auth rejected"

    def test_never_configured_ignores_a_stale_cache_from_a_previous_configuration(self):
        record_ai_check_result(LLMResult(available=True))
        health = compute_ai_status(_settings())  # nothing configured now
        assert health.status == "NOT CONFIGURED"


class TestVoiceStatus:
    def test_not_configured_by_default(self):
        health = compute_voice_status(_settings())
        assert health.status == "NOT CONFIGURED"

    def test_declared_intent_with_no_recorded_load_result_is_degraded_not_connected(self):
        """A real provider (services/voice/voice/providers/real.py) now
        exists, but this unit test never runs `build_and_start_voice_
        pipeline` — the process-global load-result registry stays empty,
        which must never be silently reported as CONNECTED."""
        health = compute_voice_status(_settings(stt_provider="whisper_cpp"))
        assert health.status == "DEGRADED"
        assert "whisper_cpp" in health.reason
        assert "has not finished initializing" in health.reason

    def test_connected_when_all_three_real_components_loaded(self):
        record_voice_wake_word_status(VoiceComponentStatus(True, "wake word ok"))
        record_voice_stt_status(VoiceComponentStatus(True, "stt ok"))
        record_voice_tts_status(VoiceComponentStatus(True, "tts ok"))
        health = compute_voice_status(
            _settings(
                stt_provider="whisper_cpp",
                tts_provider="piper",
                wake_word_provider="openwakeword",
            )
        )
        assert health.status == "CONNECTED"
        assert "wake word ok" in health.reason
        reset_voice_provider_status()

    def test_degraded_when_some_real_components_loaded_and_some_failed(self):
        record_voice_wake_word_status(VoiceComponentStatus(True, "wake word ok"))
        record_voice_stt_status(VoiceComponentStatus(False, "whisper model missing"))
        health = compute_voice_status(
            _settings(stt_provider="whisper_cpp", wake_word_provider="openwakeword")
        )
        assert health.status == "DEGRADED"
        assert "whisper model missing" in health.reason
        reset_voice_provider_status()

    def test_error_when_the_only_declared_component_failed_to_load(self):
        record_voice_stt_status(VoiceComponentStatus(False, "whisper model missing"))
        health = compute_voice_status(_settings(stt_provider="whisper_cpp"))
        assert health.status == "ERROR"
        reset_voice_provider_status()


class TestVisionStatus:
    def test_not_configured_when_nothing_available(self, monkeypatch):
        monkeypatch.setattr("app.services.subsystem_health._ocr_available", lambda: False)
        monkeypatch.setattr(
            "app.services.subsystem_health._screen_capture_available", lambda: False
        )
        health = compute_vision_status(_settings())
        assert health.status == "NOT CONFIGURED"

    def test_degraded_when_ocr_or_capture_available_but_no_model(self, monkeypatch):
        monkeypatch.setattr("app.services.subsystem_health._ocr_available", lambda: True)
        monkeypatch.setattr(
            "app.services.subsystem_health._screen_capture_available", lambda: False
        )
        health = compute_vision_status(_settings())
        assert health.status == "DEGRADED"
        assert "OCR available" in health.reason

    def test_declared_model_provider_without_real_implementation_is_honest(self, monkeypatch):
        monkeypatch.setattr("app.services.subsystem_health._ocr_available", lambda: True)
        monkeypatch.setattr("app.services.subsystem_health._screen_capture_available", lambda: True)
        health = compute_vision_status(_settings(vision_provider="some-model"))
        assert health.status == "DEGRADED"
        assert "some-model" in health.reason
        assert "no real vision-model implementation" in health.reason


class TestComputerControlStatus:
    def test_not_enabled_when_permission_flag_off(self):
        health = compute_computer_control_status(
            enabled_flag=False, capabilities=_capabilities(is_windows=True)
        )
        assert health.status == "NOT ENABLED"

    def test_disabled_when_enabled_but_platform_unsupported(self):
        health = compute_computer_control_status(
            enabled_flag=True, capabilities=_capabilities(is_windows=False)
        )
        assert health.status == "DISABLED"
        assert "requires Windows" in health.reason

    def test_connected_when_enabled_and_windows(self):
        health = compute_computer_control_status(
            enabled_flag=True, capabilities=_capabilities(is_windows=True)
        )
        assert health.status == "CONNECTED"

    def test_flag_off_wins_even_on_windows(self):
        # The permission gate is the primary, actionable reason — report
        # it even when the platform would otherwise support automation.
        health = compute_computer_control_status(
            enabled_flag=False, capabilities=_capabilities(is_windows=True)
        )
        assert health.status == "NOT ENABLED"


class TestBrowserStatus:
    def test_not_connected_with_no_open_sessions(self):
        manager = BrowserManager(adapter_factory=FakeBrowserAdapter)
        health = compute_browser_status(manager)
        assert health.status in ("NOT CONNECTED", "NOT CONFIGURED")

    async def test_connected_with_a_real_open_session(self):
        manager = BrowserManager(adapter_factory=FakeBrowserAdapter)
        await manager.launch()
        try:
            health = compute_browser_status(manager)
            assert health.status == "CONNECTED"
            assert "1 browser session" in health.reason
        finally:
            await manager.close_all()

    def test_not_configured_when_playwright_is_not_installed(self, monkeypatch):
        manager = BrowserManager(adapter_factory=FakeBrowserAdapter)
        monkeypatch.setattr(
            "app.services.subsystem_health.importlib.util.find_spec", lambda name: None
        )
        health = compute_browser_status(manager)
        assert health.status == "NOT CONFIGURED"


class TestIoTStatus:
    def test_not_connected_with_no_paired_devices(self):
        service = DevicePairingService(credential_manager=None)  # type: ignore[arg-type]
        health = compute_iot_status(service)
        assert health.status == "NOT CONNECTED"

    def test_connected_once_a_device_has_an_active_permission(self):
        service = DevicePairingService(credential_manager=None)  # type: ignore[arg-type]
        service._permission_cache[("device-1", "power")] = None  # never expires
        health = compute_iot_status(service)
        assert health.status == "CONNECTED"

    def test_not_connected_when_the_only_permission_has_expired(self):
        from datetime import UTC, datetime, timedelta

        service = DevicePairingService(credential_manager=None)  # type: ignore[arg-type]
        service._permission_cache[("device-1", "power")] = datetime.now(UTC) - timedelta(hours=1)
        health = compute_iot_status(service)
        assert health.status == "NOT CONNECTED"
