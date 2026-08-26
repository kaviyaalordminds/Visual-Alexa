# Model Routing

`ModelRouter` (`app/services/agent/model_router.py`) — brief §34: "Do not
implement aggressive routing complexity yet. Provide a clean
abstraction."

## 1. Current behavior

`route(goal, risk_level) -> RoutingDecision`. With only
`NotConfiguredLLMProvider` active (`isinstance` check), every route
resolves to `"deterministic"` with the reason "No LLM provider is
configured." — honest, not a placeholder pretending to route
intelligently.

## 2. Why the abstraction exists now, complexity later

The brief's own routing examples (simple → local, complex → cloud,
sensitive → local, vision-heavy → vision-capable provider) all require a
second real provider to route *to* — none exists yet. Building the
routing logic against a single always-deterministic outcome would either
be untestable (no second path to compare against) or speculative (guessing
at a future provider's characteristics). The `RoutingDecision` shape
(`route`, `reason`) is stable — a future provider changes `route`'s body,
not its signature or any caller.

## 3. Not implemented

Any actual multi-provider decision logic — this is a deliberate Phase 4
scope boundary, not an oversight, matching brief §34 literally.
