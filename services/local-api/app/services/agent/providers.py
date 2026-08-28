"""CloudLLMProvider — the one real `LLMProvider` adapter this build ships,
alongside `llm_provider.NotConfiguredLLMProvider`. docs/subsystem-activation/AI-STATUS.md.

CLAUDE.md: "No vendor-specific AI SDK may be imported outside its
designated provider adapter module" — this *is* that module, and it
deliberately imports no vendor SDK at all: it speaks a generic
OpenAI-compatible chat-completions HTTP API via `httpx`, which is how
OpenAI itself, most OpenAI-compatible cloud providers, and a local
Ollama/LM Studio-style server can all be reached with the same client.
Which provider is actually configured is a runtime choice
(`Settings.ai_provider/ai_model/ai_api_key/ai_base_url`), never a
hard-coded vendor.

Two distinct operations, deliberately kept separate (docs/subsystem-
activation/AI-STATUS.md "AI HEALTH CHECK" vs "AI TEST"):

- `health_check()` — a cheap, read-only GET against the provider's model
  list. Safe to call reasonably often; used to answer "is this reachable"
  without paying for an inference call.
- `understand()`/`plan()`/`reason()`/`summarize()`/`classify()` — the real
  `LLMProvider` Protocol methods, each a genuine (billable) inference
  call. Never called automatically or on a timer — only in response to an
  explicit user/tool action (the `system.ai_health_check` tool's "send a
  trivial test message" step, or a future planner integration).

Never logs or returns the API key in any `LLMResult.reason` — every
failure path below returns a message built only from the exception's
`str()`/status code, and httpx never includes the Authorization header's
value in its own exception messages.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.services.agent.llm_provider import LLMProvider, LLMResult, NotConfiguredLLMProvider

_HEALTH_CHECK_TIMEOUT_SECONDS = 3.0
_INFERENCE_TIMEOUT_SECONDS = 15.0


class CloudLLMProvider:
    """Real `LLMProvider` implementation, real HTTP calls to whatever
    OpenAI-compatible endpoint the operator configured. Never raises out
    of any of its public methods — every failure mode (unreachable host,
    auth failure, timeout, malformed response) becomes a normal
    `LLMResult(available=False, reason=...)`, matching
    `NotConfiguredLLMProvider`'s own "fail gracefully, never crash"
    contract (brief §32)."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        # Test-only seam: a real deployment never passes this, so
        # httpx.AsyncClient falls back to its normal default transport
        # (a real network connection). Tests inject an httpx.MockTransport
        # instead of monkeypatching httpx globally.
        self._transport = transport

    async def health_check(self) -> LLMResult:
        """Cheap reachability probe — GET .../models, no inference, no
        per-token cost. This is what `/system` and the `ai_health_check`
        tool use; it is never called on an automatic timer (see this
        module's docstring)."""
        try:
            async with httpx.AsyncClient(
                timeout=_HEALTH_CHECK_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            if response.status_code == 200:
                return LLMResult(available=True, content="reachable")
            if response.status_code in (401, 403):
                return LLMResult(
                    available=False,
                    reason=f"Provider rejected the configured credentials "
                    f"(HTTP {response.status_code}).",
                )
            return LLMResult(
                available=False,
                reason=f"Provider responded with HTTP {response.status_code}.",
            )
        except httpx.TimeoutException:
            return LLMResult(
                available=False,
                reason=f"Provider did not respond within {_HEALTH_CHECK_TIMEOUT_SECONDS:.0f}s.",
            )
        except httpx.HTTPError as exc:
            return LLMResult(
                available=False, reason=f"Provider unreachable: {exc.__class__.__name__}."
            )

    async def _complete(self, messages: list[dict[str, str]]) -> LLMResult:
        try:
            async with httpx.AsyncClient(
                timeout=_INFERENCE_TIMEOUT_SECONDS, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self._model, "messages": messages, "max_tokens": 256},
                )
            if response.status_code != 200:
                return LLMResult(
                    available=False,
                    reason=f"Provider responded with HTTP {response.status_code}.",
                )
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return LLMResult(available=True, content=content)
        except httpx.TimeoutException:
            return LLMResult(
                available=False,
                reason=f"Provider did not respond within {_INFERENCE_TIMEOUT_SECONDS:.0f}s.",
            )
        except httpx.HTTPError as exc:
            return LLMResult(
                available=False, reason=f"Provider unreachable: {exc.__class__.__name__}."
            )
        except (KeyError, IndexError, ValueError):
            return LLMResult(
                available=False, reason="Provider returned an unexpected response shape."
            )

    async def understand(self, request: str) -> LLMResult:
        return await self._complete([{"role": "user", "content": request}])

    async def plan(self, goal: str, context: dict) -> LLMResult:
        content = f"Goal: {goal}\nContext: {context}"
        return await self._complete([{"role": "user", "content": content}])

    async def reason(self, prompt: str, context: dict) -> LLMResult:
        return await self._complete([{"role": "user", "content": prompt}])

    async def summarize(self, text: str) -> LLMResult:
        return await self._complete([{"role": "user", "content": f"Summarize:\n{text}"}])

    async def classify(self, text: str, categories: list[str]) -> LLMResult:
        prompt = f"Classify the following text into exactly one of {categories}:\n{text}"
        return await self._complete([{"role": "user", "content": prompt}])


def build_llm_provider(settings: Settings) -> LLMProvider:
    """The one place an `LLMProvider` gets constructed from configuration.
    Returns `NotConfiguredLLMProvider` (never raises, never a network
    call) unless every piece required to reach a real provider is
    actually present."""
    if settings.ai_provider and settings.ai_api_key and settings.ai_model and settings.ai_base_url:
        return CloudLLMProvider(
            base_url=settings.ai_base_url, api_key=settings.ai_api_key, model=settings.ai_model
        )
    return NotConfiguredLLMProvider()
