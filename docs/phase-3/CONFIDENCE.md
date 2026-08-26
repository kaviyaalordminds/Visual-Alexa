# Confidence

`vision.core.confidence` (`vision/core/confidence.py`) — a configurable
HIGH/MEDIUM/LOW confidence model, not a hard-coded magic-number split.

## 1. Base scores per evidence tier

`_BASE_SCORE_BY_TIER` assigns a 0-1 base score to each
`veyra_contracts.EvidenceTier`, strictly decreasing down
`docs/architecture/05-COMPUTER-CONTROL.md` §1's priority order:
`NATIVE_API` 0.98 → `UI_AUTOMATION` 0.95 → `BROWSER_DOM` 0.9 →
`ACCESSIBILITY_TREE`/`APP_INTEGRATION` 0.85 → `OCR` 0.6 →
`VISION_MODEL` 0.55 → `COORDINATE` 0.2.

## 2. Bands and thresholds

`ConfidenceThresholds` (a frozen dataclass, injectable — "configurable")
defines `high_at_or_above` (0.85), `medium_at_or_above` (0.5), and
`confirmation_required_below` (0.85). `score_to_band` maps a raw score to
`veyra_contracts.Confidence.{HIGH,MEDIUM,LOW}`.

## 3. Low confidence never authorizes a sensitive action automatically

`requires_confirmation(score)` — the one function callers must consult
before treating a grounded target as safe to act on.
`ObservationCoordinator.requires_fresh_confirmation(element)` exposes this
directly for a `GroundedElement`. This is documented as the hook a future
Phase 4 planner (and Phase 2's own SENSITIVE/CRITICAL confirmation path)
must call — Phase 3 itself never executes an action, so nothing in this
phase can yet violate the rule, but the enforcement point is built and
unit-tested now (`tests/unit/test_vision_confidence.py`).

## 4. Combination

`combine_scores` — see `PERCEPTION-FUSION.md` §2.
