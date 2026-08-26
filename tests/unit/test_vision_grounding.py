"""docs/phase-3/VISUAL-GROUNDING.md — mandatory ambiguity handling. Directly
exercises the brief's Second Acceptance Test scenario (Download / Download
PDF / Download Image -> AMBIGUOUS_TARGET, never a guess) and the Final
Acceptance Test shape (a single clear match -> GROUNDED)."""

from __future__ import annotations

from computer_control.core.models import Rect
from vision.core.grounding import GroundingEngine
from vision.core.models import GroundedElement, TargetDescription


def _element(name: str, role: str, score: float, left: int = 0) -> GroundedElement:
    return GroundedElement(
        name=name,
        role=role,
        text=name,
        bounds=Rect(left=left, top=0, width=80, height=20),
        confidence_score=score,
    )


def test_single_clear_match_is_grounded():
    engine = GroundingEngine()
    elements = [
        _element("Download", "button", 0.95),
        _element("Settings", "button", 0.9, left=100),
    ]
    result = engine.ground(TargetDescription(text="Download"), elements)
    assert result.status == "GROUNDED"
    assert result.target is not None
    assert result.target.name == "Download"


def test_ambiguous_download_variants_never_guessed():
    engine = GroundingEngine()
    elements = [
        _element("Download", "button", 0.9),
        _element("Download PDF", "button", 0.9, left=100),
        _element("Download Image", "button", 0.9, left=200),
    ]
    result = engine.ground(TargetDescription(text="Download"), elements)
    assert result.status == "AMBIGUOUS_TARGET"
    assert result.target is None
    assert len(result.candidates) == 3


def test_no_match_is_not_found():
    engine = GroundingEngine()
    result = engine.ground(TargetDescription(text="Nonexistent"), [_element("Save", "button", 0.9)])
    assert result.status == "NOT_FOUND"


def test_empty_target_description_is_not_found_not_a_crash():
    engine = GroundingEngine()
    result = engine.ground(TargetDescription(), [_element("Save", "button", 0.9)])
    assert result.status == "NOT_FOUND"


def test_role_narrows_an_existing_text_match_set():
    engine = GroundingEngine()
    elements = [
        _element("Save", "button", 0.9),
        _element("Save", "menuitem", 0.9, left=100),
    ]
    result = engine.ground(TargetDescription(text="Save", role="button"), elements)
    assert result.status == "GROUNDED"
    assert result.target.role == "button"


def test_find_by_semantics_ranks_by_keyword_overlap():
    engine = GroundingEngine()
    elements = [
        _element("Download file", "button", 0.5),
        _element("Cancel", "button", 0.5, left=100),
    ]
    found = engine.find_by_semantics(elements, "download the file")
    assert found and found[0].name == "Download file"


def test_best_match_clearly_best_candidate_wins_no_ambiguity():
    engine = GroundingEngine()
    elements = [
        _element("Download", "button", 0.95),
        _element("Download Now", "button", 0.5, left=100),
    ]
    result = engine.best_match(elements)
    assert result.status == "GROUNDED"
    assert result.target.confidence_score == 0.95
