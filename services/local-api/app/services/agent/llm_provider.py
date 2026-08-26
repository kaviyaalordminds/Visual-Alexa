"""LLMProvider — provider-independent AI reasoning abstraction.
docs/phase-4/MODEL-ABSTRACTION.md.

No real provider ships in Phase 4 (docs/phase-4/PHASE-4-IMPLEMENTATION-PLAN.md
§4), mirroring Phase 3's `VisionProvider`/`NotConfiguredVisionProvider`
precedent exactly. `NotConfiguredLLMProvider` never raises and never makes
a network call — brief §32: 'If no model is configured, the application
must fail gracefully. Do not crash.' The deterministic `IntentInterpreter`/
`TaskPlanner` do not call this Protocol at all; they are Phase 4's
'works without a model' path.
"""

from __future__ import annotations

from typing import Protocol


class LLMResult:
    def __init__(
        self, *, available: bool, content: str | None = None, reason: str | None = None
    ) -> None:
        self.available = available
        self.content = content
        self.reason = reason


class LLMProvider(Protocol):
    """CLAUDE.md: 'No vendor-specific AI SDK may be imported outside its
    designated provider adapter module' — a future real provider
    (local/OpenAI-compatible/Anthropic-compatible/Gemini) implements this
    exact Protocol in its own adapter module, never imported from here."""

    async def understand(self, request: str) -> LLMResult: ...
    async def plan(self, goal: str, context: dict) -> LLMResult: ...
    async def reason(self, prompt: str, context: dict) -> LLMResult: ...
    async def summarize(self, text: str) -> LLMResult: ...
    async def classify(self, text: str, categories: list[str]) -> LLMResult: ...


class NotConfiguredLLMProvider:
    """The only `LLMProvider` Phase 4 ships."""

    async def understand(self, request: str) -> LLMResult:
        return LLMResult(available=False, reason="No LLM provider configured.")

    async def plan(self, goal: str, context: dict) -> LLMResult:
        return LLMResult(available=False, reason="No LLM provider configured.")

    async def reason(self, prompt: str, context: dict) -> LLMResult:
        return LLMResult(available=False, reason="No LLM provider configured.")

    async def summarize(self, text: str) -> LLMResult:
        return LLMResult(available=False, reason="No LLM provider configured.")

    async def classify(self, text: str, categories: list[str]) -> LLMResult:
        return LLMResult(available=False, reason="No LLM provider configured.")
