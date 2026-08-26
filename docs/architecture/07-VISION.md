# 07 — Vision Architecture

## 1. Components (future; interfaces defined now)

```
ScreenCapture         # explicit-enable-only screenshot capture
OCREngine               # text extraction from captured regions
UIElementDetector        # structured element detection (feeds evidence tier 6-7)
AccessibilityTreeReader    # Windows UIA/MSAA tree reader (tier 2-3; shared
                       # with 05-COMPUTER-CONTROL.md controllers)
WindowIdentifier             # which window/app is in focus
ApplicationIdentifier          # what application a window belongs to
VisualGroundingModel              # vision-language model reasoning over
                       # a screenshot (tier 7)
TemporalStateComparator             # diff current vs. previous observation
                       # to detect "did the UI change since I last looked"
```

## 2. Adaptive observation strategy

Continuously streaming full-screen captures to a cloud vision model is
explicitly disallowed as a default behavior (product brief §14). Observation
intensity scales with task state:

| System state | Observation behavior |
|---|---|
| IDLE (no active task) | No screen observation. Screen capture is OFF by default and requires explicit enablement (`docs/security/05-DATA-PROTECTION.md`). |
| TASK ACTIVE | Observation scoped to the relevant window/region, at a cadence tied to the task's OBSERVE step — not continuous streaming. |
| CRITICAL ACTION pending | Explicit, single, targeted visual verification capture immediately before/after the action, never a standing stream. |

This mapping is enforced by the Task Runtime's OBSERVE step
(`14-TASK-LIFECYCLE.md`) requesting captures on demand, rather than a
capture service running unconditionally in the background.

## 3. Relationship to the evidence hierarchy

Vision (tier 7) and OCR (tier 6) are explicitly lower-priority than
structured sources per `05-COMPUTER-CONTROL.md`. This document defines the
capability; it does not change the priority ordering.

## 4. Privacy defaults

- Screen capture: OFF unless explicitly enabled per-session or persistently
  by the user, visible in the status UI (`Vision: NOT CONFIGURED` is the
  Phase 1 default and stays true until a user turns it on in a later phase).
- Captured frames are never sent to a cloud vision model without the AI mode
  being HYBRID/CLOUD and the user having explicitly enabled vision.
- No captured frame is persisted to disk by default; any future
  "save for debugging" capability must be opt-in and clearly labeled.

## 5. Phase 1 scope

Delivered: interfaces, the adaptive-observation state mapping, and privacy
defaults reflected in `SystemSetting` schema (`Vision: NOT ENABLED` is a
first-class settings value). Not delivered: any actual capture, OCR, or
vision-model integration.
