"""Configurable HIGH/MEDIUM/LOW confidence model. docs/phase-3/CONFIDENCE.md.

CLAUDE.md / docs/phase-3 §21: low confidence must never trigger a
sensitive action automatically — this module only *scores* observations;
it is `GroundingEngine`/`ObservationCoordinator` (and, in a future phase,
the AI planner + Policy Engine) that must consult
`ConfidenceThresholds.confirmation_required_below` before treating a
grounded target as safe to act on.
"""

from __future__ import annotations

from dataclasses import dataclass

from veyra_contracts import Confidence, EvidenceTier

# docs/architecture/05-COMPUTER-CONTROL.md §1 — structured (tier 1-5)
# sources are inherently more trustworthy than OCR/vision/coordinate (tier
# 6-8) ones; this is the base score a single source contributes before any
# fusion combination, on a 0-1 scale.
_BASE_SCORE_BY_TIER: dict[EvidenceTier, float] = {
    EvidenceTier.NATIVE_API: 0.98,
    EvidenceTier.UI_AUTOMATION: 0.95,
    EvidenceTier.ACCESSIBILITY_TREE: 0.85,
    EvidenceTier.APP_INTEGRATION: 0.85,
    EvidenceTier.BROWSER_DOM: 0.9,
    EvidenceTier.OCR: 0.6,
    EvidenceTier.VISION_MODEL: 0.55,
    EvidenceTier.COORDINATE: 0.2,
}


@dataclass(frozen=True)
class ConfidenceThresholds:
    """Configurable per docs/phase-3 §21 ('configurable HIGH/MEDIUM/LOW
    confidence model') — not a hard-coded magic-number split."""

    high_at_or_above: float = 0.85
    medium_at_or_above: float = 0.5
    # Anything strictly below this must never authorize a sensitive/
    # critical action without fresh user confirmation, regardless of how
    # the caller otherwise interprets HIGH/MEDIUM/LOW.
    confirmation_required_below: float = 0.85


DEFAULT_THRESHOLDS = ConfidenceThresholds()


def base_score_for_tier(tier: EvidenceTier) -> float:
    return _BASE_SCORE_BY_TIER.get(tier, 0.3)


def score_to_band(
    score: float, thresholds: ConfidenceThresholds = DEFAULT_THRESHOLDS
) -> Confidence:
    if score >= thresholds.high_at_or_above:
        return Confidence.HIGH
    if score >= thresholds.medium_at_or_above:
        return Confidence.MEDIUM
    return Confidence.LOW


def combine_scores(scores: list[float]) -> float:
    """docs/phase-3 §19 — multiple sources agreeing on the same element
    raises combined confidence above any single source's score, but never
    above 1.0, and a single low-confidence source alone never gets boosted
    just because it's the only one. Uses a simple noisy-OR: the
    probability that *at least one* independent source is right."""
    if not scores:
        return 0.0
    product_of_misses = 1.0
    for score in scores:
        product_of_misses *= 1.0 - max(0.0, min(1.0, score))
    return 1.0 - product_of_misses


def requires_confirmation(
    score: float, thresholds: ConfidenceThresholds = DEFAULT_THRESHOLDS
) -> bool:
    return score < thresholds.confirmation_required_below
