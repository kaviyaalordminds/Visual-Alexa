"""Worked fixture for the ambiguity-resolution contract, product brief §6.7:

    "Send the file to Arun."
    If multiple Aruns exist: DO NOT guess. Ask: "Which Arun do you mean?"

No live planner exists in Phase 1 to run a real conversation through, so
this fixture specifies and tests the pure `resolve_ambiguity` contract
(docs/architecture/03-AI-ARCHITECTURE.md §6) that any future planner must
call before executing a tool whose target could resolve to multiple
entities. This is the "one worked fixture as a specification" promised in
docs/research/07-VEYRA-DIFFERENTIATORS.md item 8.
"""

from veyra_contracts import AmbiguityCandidate, resolve_ambiguity


def test_single_arun_resolves_without_asking():
    candidates = [AmbiguityCandidate(id="contact-1", label="Arun Kumar")]
    resolution = resolve_ambiguity(candidates, target_description="Arun")
    assert resolution.resolved is True
    assert resolution.candidate.id == "contact-1"
    assert resolution.clarifying_question is None


def test_two_aruns_are_never_guessed_between():
    """EXPECTED: ask clarification. NOT: choose randomly."""
    candidates = [
        AmbiguityCandidate(id="contact-1", label="Arun Kumar"),
        AmbiguityCandidate(id="contact-2", label="Arun Prakash"),
    ]
    resolution = resolve_ambiguity(candidates, target_description="Arun")
    assert resolution.resolved is False
    assert resolution.candidate is None
    assert resolution.clarifying_question is not None
    assert "Arun Kumar" in resolution.clarifying_question
    assert "Arun Prakash" in resolution.clarifying_question


def test_no_match_asks_for_clarification_rather_than_failing_silently():
    resolution = resolve_ambiguity([], target_description="Arun")
    assert resolution.resolved is False
    assert resolution.clarifying_question is not None
