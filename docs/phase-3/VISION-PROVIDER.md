# Vision Provider

## 1. Abstraction only — no real provider ships in Phase 3

`vision.core.vision_provider.VisionProvider` is a `Protocol`
(`analyze_image`, `detect_elements`, `describe_scene`, `locate_target`).
The **only** implementation Phase 3 ships is `NotConfiguredVisionProvider`,
which always returns a structured "vision unavailable" result — it never
raises, and it never makes a network call, mirroring Phase 1's
`ai.mode: NOT CONFIGURED` status pattern. This directly satisfies the
brief's §57 exclusion ("no unrestricted cloud vision") and §15-17's
request for the *abstraction* and *policy gate* a future provider must
pass through, not a shipped model.

## 2. Why this doesn't limit the pipeline much

`ObservationCoordinator` is built so UIA + OCR + metadata alone already
answer the large majority of grounding questions — `decide_next_tier`
(`vision/coordinator.py`) only escalates to the vision tier when both
higher tiers produced `NOT_FOUND`, and skips the call entirely (via an
`isinstance(..., NotConfiguredVisionProvider)` fast-path) when no real
provider is configured, so "no vision model installed" never turns into
extra latency for a call that would be `NotConfiguredVisionProvider`'s
`[]`/`available=False` stub anyway.

## 3. Future providers

Local model, OpenAI-compatible, Anthropic-compatible, and Gemini providers
all implement the same four-method `Protocol` — no vendor-specific SDK is
imported outside a future provider adapter module, per `CLAUDE.md`'s
"no vendor-specific AI SDK... outside its designated provider adapter
module" rule.

## 4. Cloud gate (documented now, enforced when a provider ships)

Per brief §16-17 and `PHASE-3-IMPLEMENTATION-PLAN.md` §6: when a real
*cloud* provider is added, `vision.analyze`/`vision.locate` must become
SENSITIVE risk tier (fresh confirmation, not silently SAFE) and the
request path must be Policy → Privacy Check → Config → Redaction →
Provider — never a direct call from a tool executor to a cloud SDK. This
is a design commitment for the provider that adds cloud vision, not code
shipped in Phase 3, since no such provider exists yet to enforce it
against.

## 5. Local-first guarantee

With only `NotConfiguredVisionProvider` active, `screen.observe` and
`target.ground` both fully function using UIA + OCR alone — verified via
`tests/integration/test_vision_tools_api.py` (grounding a target from a
seeded UI tree with no vision provider involved at all) and
`tests/security/test_phase3_prompt_injection.py::test_vision_provider_not_configured_no_cloud_upload_possible`.
