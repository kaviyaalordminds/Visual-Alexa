"""docs/phase-3/CONFIDENCE.md — pure logic, no OS dependency."""

from __future__ import annotations

from veyra_contracts import Confidence, EvidenceTier
from vision.core.confidence import (
    DEFAULT_THRESHOLDS,
    base_score_for_tier,
    combine_scores,
    requires_confirmation,
    score_to_band,
)


def test_structured_sources_score_higher_than_ocr_and_coordinate():
    assert base_score_for_tier(EvidenceTier.NATIVE_API) > base_score_for_tier(EvidenceTier.OCR)
    assert base_score_for_tier(EvidenceTier.OCR) > base_score_for_tier(EvidenceTier.COORDINATE)


def test_score_to_band_thresholds():
    assert score_to_band(0.95) == Confidence.HIGH
    assert score_to_band(0.6) == Confidence.MEDIUM
    assert score_to_band(0.1) == Confidence.LOW


def test_combine_scores_multiple_sources_raises_confidence():
    single = combine_scores([0.6])
    combined = combine_scores([0.6, 0.6])
    assert combined > single
    assert combined <= 1.0


def test_combine_scores_empty_is_zero():
    assert combine_scores([]) == 0.0


def test_low_confidence_requires_confirmation():
    assert requires_confirmation(0.2, DEFAULT_THRESHOLDS) is True
    assert requires_confirmation(0.99, DEFAULT_THRESHOLDS) is False
