# Perception Fusion

`vision.core.fusion.PerceptionFusion` (`vision/core/fusion.py`) merges
same-element detections from UI Automation nodes, OCR text regions, and
vision-model regions into `GroundedElement`s.

## 1. Matching

Two detections are considered the same element when their bounding boxes'
intersection-over-union is ≥ `overlap_threshold` (default 0.5). This is
pure geometry (`_overlap_ratio`), no ML, deliberately simple and
explainable.

## 2. Combining

- `sources`: every contributing `EvidenceTier`, deduplicated, order
  preserved.
- `confidence_score`: `combine_scores` (`vision/core/confidence.py`) — a
  noisy-OR combination (`1 - Π(1 - score_i)`), so agreement across sources
  raises confidence above any single source, but never above 1.0, and a
  single source is never boosted just because it's alone.
- `privacy_level`: the most sensitive level across the group (a password
  field detected by only one of several overlapping sources still marks
  the fused element SECRET).
- Non-overlapping detections are never merged, even if adjacent.

## 3. Verified

`tests/unit/test_vision_fusion.py` — overlapping UIA+OCR merge into one
element carrying both `EvidenceTier`s; non-overlapping regions stay
separate; fused confidence is at least as high as the best single source;
a password-flagged UIA node marks the fused element `privacy_level:
SECRET`. All pure Python, no OS dependency, genuinely exercised.
