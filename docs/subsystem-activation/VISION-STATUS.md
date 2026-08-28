# Vision Subsystem Status

**Current status in this environment: DEGRADED**
Reason: OCR is genuinely available (a real `tesseract` binary is
installed); screen capture is unavailable (no `DISPLAY`, non-Windows); no
vision *model* provider is configured, so AI-driven scene understanding
doesn't work. Basic screen reading works.

## Architecture

```
Screen -> Screenshot Capture (mss) -> OCR (tesseract, real) -> Structured Observation -> AI/Computer Agent
                                    -> VisionProvider (model) -> richer scene understanding, not configured
```

Two genuinely different capability tiers, checked independently
(`compute_vision_status()`, `app/services/subsystem_health.py`):

1. **OCR/capture** — already real, already tested
   (`services/vision/vision/ocr/engine.py`, real `pytesseract`+tesseract;
   `MssScreenBackend`, real cross-platform screen capture). This
   activation added the health-check layer (`shutil.which("tesseract")`,
   a platform/`DISPLAY` check) — it did not touch the OCR/capture code
   itself, which was already correct.
2. **Vision model** (`VisionProvider` Protocol,
   `services/vision/vision/core/vision_provider.py`) — object/element
   detection, scene description. Ships only `NotConfiguredVisionProvider`.
   `VEYRA_VISION_PROVIDER` (added this activation) declares intent; no
   real model implementation exists yet.

## Why DEGRADED, not NOT CONFIGURED or CONNECTED

Neither extreme would be honest: NOT CONFIGURED would hide that OCR
genuinely works today; CONNECTED would falsely claim AI-driven scene
understanding that doesn't exist. DEGRADED is the accurate middle state —
matches the Phase 10 brief's own status vocabulary exactly.

## Testing vision today

The existing screen-capture/OCR tools from Phase 2/3 already work (no new
tool was needed — see `services/computer_control`'s screen tools and
`app/services/vision`'s registered tools). Invoke the existing capture
tool via `/tools/{screen-capture-tool-id}/invoke` to exercise real OCR
against a real screenshot on a machine with a display. `GET /system`'s
`vision`/`details.vision` fields report the same real capability check
without capturing anything.

## How to make vision fully CONNECTED in a future phase

Implement a real `VisionProvider` (a multimodal model call, local or
cloud) in a new adapter module, following the exact pattern
`app/services/agent/providers.py`'s `CloudLLMProvider` established for
AI — then `compute_vision_status()` reports CONNECTED once that provider
is genuinely configured and (like AI) verified reachable, not merely
declared.
