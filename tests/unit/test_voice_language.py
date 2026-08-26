"""docs/phase-5/LANGUAGE-DETECTION.md, brief §20-22 — tested directly
against the brief's own worked examples. Brief's own warning applies:
"Do not claim language accuracy without actual testing" — this is exactly
that testing, scoped to the sentences the brief itself specifies."""

from __future__ import annotations

from voice.core.enums import Language
from voice.core.language import LanguageDetector, detect_language


def test_plain_english_is_en():
    result = detect_language("Open Chrome.")
    assert result.language == Language.EN
    assert result.mixed_language is False


def test_tanglish_pannu_is_ta_en():
    result = detect_language("Chrome open pannu.")
    assert result.language == Language.TA_EN
    assert result.mixed_language is True


def test_tanglish_long_sentence_is_ta_en():
    result = detect_language("Chrome open panni YouTube la AR Rahman song search pannu.")
    assert result.language == Language.TA_EN


def test_tanglish_folder_example_is_ta_en():
    result = detect_language("Veyra, Downloads folder la latest PDF open pannu.")
    assert result.language == Language.TA_EN


def test_native_tamil_script_is_ta():
    result = detect_language("க்ரோம் திற")
    assert result.language == Language.TA


def test_empty_string_is_unknown():
    result = detect_language("")
    assert result.language == Language.UNKNOWN
    assert result.confidence == 0.0


def test_detector_class_matches_pure_function():
    detector = LanguageDetector()
    assert detector.detect("Open Chrome.").language == detect_language("Open Chrome.").language
