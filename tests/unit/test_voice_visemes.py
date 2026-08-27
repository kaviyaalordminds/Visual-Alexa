"""docs/phase-6/LIP-SYNC.md — text_to_visemes is pure and deterministic;
no real TTS audio exists in this environment to drive lip sync from
(docs/phase-5/PHASE-5-TEST-RESULTS.md §5), so this approximates a mouth-
shape timeline from the real response text instead."""

from __future__ import annotations

from itertools import pairwise

from voice.core.enums import VisemeShape
from voice.core.visemes import text_to_visemes


def test_empty_text_yields_no_frames():
    assert text_to_visemes("") == []


def test_whitespace_only_text_yields_no_frames():
    assert text_to_visemes("   \n\t") == []


def test_punctuation_only_text_yields_no_frames():
    assert text_to_visemes("...!?") == []


def test_same_text_always_yields_the_same_timeline():
    a = text_to_visemes("Opening Chrome now.")
    b = text_to_visemes("Opening Chrome now.")
    assert a == b


def test_frames_are_contiguous_and_non_overlapping():
    frames = text_to_visemes("Hello there, I found your file.")
    assert frames  # non-trivial text produces at least one frame
    for prev, nxt in pairwise(frames):
        assert nxt.start_ms == prev.start_ms + prev.duration_ms


def test_every_frame_has_positive_duration():
    for frame in text_to_visemes("A quick response with several words."):
        assert frame.duration_ms > 0


def test_word_boundaries_insert_a_rest_frame():
    frames = text_to_visemes("Hi Bob")
    rest_shapes = [f.shape for f in frames if f.shape == VisemeShape.REST]
    assert rest_shapes  # at least the boundary between "Hi" and "Bob"


def test_timeline_never_ends_on_a_trailing_rest():
    frames = text_to_visemes("Done.")
    assert frames[-1].shape != VisemeShape.REST


def test_consecutive_same_bucket_letters_merge_into_one_frame():
    # "ai" -> both letters are in the AI bucket; must not emit two frames.
    frames = text_to_visemes("aim")
    shapes = [f.shape for f in frames]
    assert shapes.count(VisemeShape.AI) == 1


def test_vowel_and_consonant_classification_examples():
    single_letter_frames = {f.shape for f in text_to_visemes("a i e o u f v l m b p w q x")}
    assert VisemeShape.AI in single_letter_frames
    assert VisemeShape.E in single_letter_frames
    assert VisemeShape.OH in single_letter_frames
    assert VisemeShape.U in single_letter_frames
    assert VisemeShape.FV in single_letter_frames
    assert VisemeShape.L in single_letter_frames
    assert VisemeShape.MBP in single_letter_frames
    assert VisemeShape.WQ in single_letter_frames
    assert VisemeShape.ETC in single_letter_frames


def test_custom_speaking_rate_changes_duration_but_not_shape_sequence():
    default = text_to_visemes("Testing rate changes.")
    faster = text_to_visemes("Testing rate changes.", chars_per_minute=1800)
    assert [f.shape for f in default] == [f.shape for f in faster]
    assert sum(f.duration_ms for f in faster) <= sum(f.duration_ms for f in default)
