"""docs/phase-5/TTS.md, brief §37-41 — PronunciationDictionary rewrites
known terms for TTS only; it must never alter unrelated text."""

from __future__ import annotations

from voice.core.pronunciation import PronunciationDictionary, apply_pronunciations


def test_veyra_gets_phonetic_spelling():
    assert apply_pronunciations("VEYRA is ready.") == "Vay-rah is ready."


def test_vs_code_and_github_are_split_for_pronunciation():
    result = apply_pronunciations("Open VS Code and check GitHub.")
    assert result == "Open V S Code and check Git Hub."


def test_case_insensitive_match_uses_canonical_spelling():
    assert apply_pronunciations("veyra") == "Vay-rah"


def test_unrelated_text_is_untouched():
    text = "Search Downloads for the latest PDF."
    assert apply_pronunciations(text) == text


def test_multiple_terms_in_one_sentence():
    result = apply_pronunciations("Ask Claude about OpenAI on YouTube.")
    assert result == "Ask Clawd about Open A I on You Tube."


def test_dictionary_class_matches_pure_function():
    dictionary = PronunciationDictionary()
    assert dictionary.apply("VEYRA") == apply_pronunciations("VEYRA")
