"""ModelRouter — routes a request to the deterministic path or a
configured `LLMProvider`. docs/phase-4/MODEL-ROUTING.md.

Brief §34: 'Do not implement aggressive routing complexity yet. Provide a
clean abstraction.' With only `NotConfiguredLLMProvider` shipped
(docs/phase-4/MODEL-ABSTRACTION.md), every route resolves to
`"deterministic"` — the `RoutingDecision.reason` field exists so a future
provider can be introduced without changing this function's signature,
only its body.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.agent.llm_provider import LLMProvider, NotConfiguredLLMProvider

Route = Literal["deterministic", "llm"]


@dataclass
class RoutingDecision:
    route: Route
    reason: str


class ModelRouter:
    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self._llm_provider = llm_provider or NotConfiguredLLMProvider()

    def route(self, *, goal: str | None, risk_level: str) -> RoutingDecision:
        if isinstance(self._llm_provider, NotConfiguredLLMProvider):
            return RoutingDecision(
                route="deterministic", reason="No LLM provider is configured."
            )
        # A future provider would route complex/ambiguous requests to
        # "llm" and leave simple, template-matched or SENSITIVE-and-above
        # requests on the deterministic path (brief §34's own examples) —
        # not implemented here since no provider exists yet to route to.
        return RoutingDecision(
            route="deterministic", reason="Deterministic templates cover this request."
        )
