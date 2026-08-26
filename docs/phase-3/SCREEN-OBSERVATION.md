# Screen Observation

## 1. `screen.observe`

Tool: `screen.observe` (SAFE risk tier, gated by the
`screen_observation.enabled` system setting — the same gate every
pixel-capturing tool in this codebase uses). Implementation:
`ObservationCoordinator.observe` (`services/vision/vision/coordinator.py`).

Arguments: `window_handle?`, `include_ocr` (default `true`),
`include_vision` (default `false`). Output: one `ScreenObservation`
(`vision/core/models.py`) containing:

- `scene`: a `SceneGraph` (UI tree), when UI Automation is available.
- `text_regions`: OCR `TextRegion[]`, privacy-redacted before being
  returned (see `REDACTION.md`).
- `visual_regions`: vision-model `VisualRegion[]`, empty unless
  `include_vision=true` and a real provider is configured.
- `privacy_level`: the most sensitive `PrivacyLevel` found anywhere in the
  observation (never an average).
- `screenshot_ref`: an opaque handle into the short-lived
  `ObservationCache` (`vision/core/cache.py`) — never the raw image bytes
  themselves in the primary record.
- `stage_timings_ms` / `sources_used`: per-stage performance and
  provenance, see `PERFORMANCE.md`.

## 2. Never a raw screenshot in the primary record

Consistent with Phase 2's screen-capture tools (base64 stays in the HTTP
response only, never written to disk), `ScreenObservation` never embeds
raw image bytes in its own fields. If a future caller needs the pixels
that produced an observation, `screenshot_ref` resolves them from the
in-memory `ObservationCache`, which is capped (`max_entries`) and
TTL-expiring (`ttl_seconds`, default 60s) — see `PERFORMANCE.md` §3.

## 3. Verified vs. reviewed-only

Real, verified against a live (virtual) X display in this environment:
`mss`-based capture, OCR extraction, fusion, privacy classification. The
UI-tree portion of an observation is populated only when
`bundle.ui_automation is not None`, i.e. only on a real Windows host — on
this Linux container `scene` is `None` and `sources_used` correctly omits
`UI_AUTOMATION`, which is itself the honest behavior being verified
(`tests/integration/test_vision_tools_api.py::test_screen_observe_real_capture_and_privacy_default`).
