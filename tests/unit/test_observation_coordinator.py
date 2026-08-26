"""docs/phase-3/VISUAL-PERCEPTION-ARCHITECTURE.md — the tier-escalation
policy is a pure function, tested here without any backend at all."""

from __future__ import annotations

from vision.coordinator import decide_next_tier
from vision.core.models import GroundingResult


def test_grounded_ui_result_short_circuits_before_ocr():
    ui_result = GroundingResult(status="GROUNDED")
    tier = decide_next_tier(ui_result=ui_result, ocr_attempted=False, vision_available=True)
    assert tier == "DONE"


def test_ambiguous_ui_result_also_short_circuits():
    ui_result = GroundingResult(status="AMBIGUOUS_TARGET")
    tier = decide_next_tier(ui_result=ui_result, ocr_attempted=False, vision_available=True)
    assert tier == "DONE"


def test_not_found_escalates_to_ocr_first():
    ui_result = GroundingResult(status="NOT_FOUND")
    tier = decide_next_tier(ui_result=ui_result, ocr_attempted=False, vision_available=True)
    assert tier == "OCR"


def test_not_found_after_ocr_escalates_to_vision_if_available():
    ui_result = GroundingResult(status="NOT_FOUND")
    tier = decide_next_tier(ui_result=ui_result, ocr_attempted=True, vision_available=True)
    assert tier == "VISION"


def test_not_found_after_ocr_stops_if_no_vision_provider():
    ui_result = GroundingResult(status="NOT_FOUND")
    tier = decide_next_tier(ui_result=ui_result, ocr_attempted=True, vision_available=False)
    assert tier == "DONE"
