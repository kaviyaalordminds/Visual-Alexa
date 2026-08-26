"""docs/phase-5 §23 — SpeechNormalizer. Must never invent entities, only
clean up what was actually said (filler words, stutters, known mishears)."""

from __future__ import annotations

from voice.core.normalizer import SpeechNormalizer, normalize_command


def test_removes_filler_words():
    result = normalize_command("um open chrome")
    assert result.normalized_text == "open chrome"
    assert "removed filler words" in result.corrections


def test_collapses_repeated_words():
    result = normalize_command("open open the the file")
    assert result.normalized_text == "open the file"


def test_fixes_known_wake_word_mishear():
    """The mishear is corrected (recorded in `corrections`) even though
    the wake phrase itself is then stripped from the final text — the
    correction still matters for anything logging what was actually
    heard."""
    result = normalize_command("Hey Veera, tell me something")
    assert any("veyra" in c.lower() for c in result.corrections)
    result_leading = normalize_command("Hey Veera open chrome")
    assert result_leading.normalized_text == "open chrome"


def test_strips_leading_wake_phrase():
    result = normalize_command("Hey Veyra, open Chrome")
    assert result.normalized_text == "open Chrome"
    assert "stripped wake phrase" in result.corrections


def test_does_not_strip_veyra_mentioned_mid_sentence():
    result = normalize_command("tell Veyra to open Chrome")
    assert "stripped wake phrase" not in result.corrections


def test_reorders_tanglish_object_verb_pannu_to_verb_object():
    result = normalize_command("Chrome open pannu.")
    assert result.normalized_text == "open Chrome"


def test_does_not_reorder_a_multi_clause_tanglish_sentence():
    """A single-pass reorder would garble a sentence with more than one
    pannu/panni clause — left untouched rather than risk that."""
    text = "Chrome open panni YouTube la AR Rahman song search pannu."
    result = normalize_command(text)
    assert result.normalized_text == text
    assert result.corrections == []


def test_does_not_invent_or_drop_real_content():
    result = normalize_command("open project2.txt")
    assert result.normalized_text == "open project2.txt"
    assert result.corrections == []


def test_collapses_excess_whitespace():
    result = normalize_command("open    chrome   please")
    assert result.normalized_text == "open chrome please"


def test_raw_text_is_preserved_verbatim():
    result = normalize_command("um open chrome")
    assert result.raw_text == "um open chrome"


def test_normalizer_class_matches_pure_function():
    normalizer = SpeechNormalizer()
    assert normalizer.normalize("um open chrome").normalized_text == "open chrome"
