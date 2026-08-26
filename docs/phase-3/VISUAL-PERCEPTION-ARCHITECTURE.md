# Visual Perception Architecture

## 1. Pipeline

```
Request (screen.observe / target.ground / ...)
        │
        ▼
 ObservationCoordinator  (services/vision/vision/coordinator.py)
        │
        ├─ UI Automation tree   (tier 2 — computer_control.UIAutomationBackend.get_tree)
        ├─ OCR                  (tier 6 — vision.ocr.engine.OCREngine)
        └─ Vision model         (tier 7 — vision.core.vision_provider.VisionProvider)
        │
        ▼
 PerceptionFusion   → GroundedElement[] (combined sources + confidence)
        │
        ▼
 GroundingEngine (target.ground)  /  ScreenObservation (screen.observe)
        │
        ▼
 Tool Registry → Policy Engine → caller
```

Priority order matches `docs/architecture/05-COMPUTER-CONTROL.md` §1
exactly: native/UIA sources are attempted before OCR, OCR before a vision
model, and a vision model before any coordinate fallback (Phase 3 has no
coordinate fallback tool at all — same deliberate absence as Phase 2).
`ObservationCoordinator.ground_target`'s `decide_next_tier` function is the
concrete embodiment of "do not run expensive vision analysis when
structured UI info already answers the question": it only escalates past
UIA when UIA's own result is `NOT_FOUND`, and only escalates past OCR when
a real (non-stub) vision provider is configured.

## 2. Components and where they live

| Component | Module | Verified here? |
|---|---|---|
| `ObservationCoordinator` | `vision/coordinator.py` | Yes — orchestration logic against fakes/real mss |
| `OCREngine` | `vision/ocr/engine.py` | Yes — real tesseract, English + Tamil |
| `PerceptionFusion` | `vision/core/fusion.py` | Yes — pure Python |
| `GroundingEngine` | `vision/core/grounding.py` | Yes — pure Python |
| `PrivacyRedactor` / `SecretDetector` | `vision/core/privacy.py` | Yes — pure Python |
| `compute_scene_diff` | `vision/core/diff.py` | Yes — pure Python |
| Visual wait conditions | `vision/core/waiting.py` | Yes — same cancellation discipline as `computer_control.core.waiting` |
| UI tree walk (`UIAutomationBackend.get_tree`) | `computer_control/windows/ui_automation.py` | Real, reviewed; Windows-only, not runtime-verified here |
| DPI scale query | `vision/windows/dpi.py` | Real, reviewed; Windows-only, not runtime-verified here |
| `VisionProvider` | `vision/core/vision_provider.py` | Only `NotConfiguredVisionProvider` ships — see `VISION-PROVIDER.md` |

## 3. Integration with Phase 1/2

No second Tool Registry, no second Policy Engine, no new REST surface for
perception. Every capability above is exposed as a registered tool through
the existing `/tools/{id}/invoke` path
(`app/services/vision/tools.py` → `app/services/vision/register.py`,
called from `app/main.py`'s lifespan right after Phase 2's
`register_computer_control_tools`, sharing the same `BackendBundle` so
capability detection runs exactly once per process). See
`docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md` §6 for the full reasoning.

## 4. What Phase 3 does NOT do

- No coordinate-only click path — perception never bypasses Phase 2's
  selector-based input tools.
- No continuous/high-frequency screenshot loop — every capture is
  triggered by an explicit tool call.
- No persisted observation history — see `PHASE-3-IMPLEMENTATION-PLAN.md`
  §7 and `PERFORMANCE.md`.
- No real vision model — see `VISION-PROVIDER.md`.
