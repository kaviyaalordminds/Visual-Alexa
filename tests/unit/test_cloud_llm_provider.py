"""CloudLLMProvider — the one real LLMProvider adapter this build ships.
docs/subsystem-activation/AI-STATUS.md. Real HTTP-call logic exercised
against an in-process httpx.MockTransport (never a real network call),
so these tests are fast and deterministic while still exercising the
actual request/response handling code, not a hand-mocked substitute.
"""

from __future__ import annotations

import httpx
import pytest
from app.core.config import Settings
from app.services.agent.llm_provider import NotConfiguredLLMProvider
from app.services.agent.providers import CloudLLMProvider, build_llm_provider

SECRET_KEY = "sk-super-secret-do-not-leak-me"


def _provider(handler) -> CloudLLMProvider:
    return CloudLLMProvider(
        base_url="https://api.example.com/v1",
        api_key=SECRET_KEY,
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


async def test_health_check_reports_reachable_on_200():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        assert request.headers["authorization"] == f"Bearer {SECRET_KEY}"
        return httpx.Response(200, json={"data": []})

    result = await _provider(handler).health_check()
    assert result.available is True


async def test_health_check_reports_credential_rejection_without_leaking_the_key():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    result = await _provider(handler).health_check()
    assert result.available is False
    assert result.reason is not None
    assert "401" in result.reason
    assert SECRET_KEY not in result.reason


async def test_health_check_reports_other_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    result = await _provider(handler).health_check()
    assert result.available is False
    assert "503" in (result.reason or "")


async def test_health_check_survives_a_network_error_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = await _provider(handler).health_check()
    assert result.available is False
    assert SECRET_KEY not in (result.reason or "")


async def test_understand_returns_the_completion_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "pong"}}]}
        )

    result = await _provider(handler).understand("ping")
    assert result.available is True
    assert result.content == "pong"


async def test_understand_handles_a_malformed_response_shape_without_raising():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    result = await _provider(handler).understand("ping")
    assert result.available is False
    assert result.reason is not None


def test_build_llm_provider_returns_not_configured_when_anything_is_missing():
    settings = Settings(ai_provider="", ai_model="m", ai_api_key="k", ai_base_url="https://x")
    assert isinstance(build_llm_provider(settings), NotConfiguredLLMProvider)


def test_build_llm_provider_returns_cloud_provider_when_fully_configured():
    settings = Settings(
        ai_provider="openai-compatible",
        ai_model="m",
        ai_api_key="k",
        ai_base_url="https://api.example.com/v1",
    )
    assert isinstance(build_llm_provider(settings), CloudLLMProvider)


async def test_not_configured_provider_health_check_never_raises_or_calls_network():
    result = await NotConfiguredLLMProvider().health_check()
    assert result.available is False
    assert result.reason == "No LLM provider configured."


@pytest.mark.parametrize("missing_field", ["ai_provider", "ai_model", "ai_api_key", "ai_base_url"])
def test_build_llm_provider_requires_every_field(missing_field):
    fields = {
        "ai_provider": "openai-compatible",
        "ai_model": "m",
        "ai_api_key": "k",
        "ai_base_url": "https://api.example.com/v1",
    }
    fields[missing_field] = ""
    settings = Settings(**fields)
    assert isinstance(build_llm_provider(settings), NotConfiguredLLMProvider)
