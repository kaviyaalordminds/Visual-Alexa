"""Ambiguity resolution contract. docs/architecture/03-AI-ARCHITECTURE.md §6:
'Before planning a tool call whose target could resolve to more than one
concrete entity ... the planner must run an AmbiguityCheck.' This module is
the pure, testable contract; no live planner calls it yet in Phase 1 — see
tests/agent-evals for the worked "send file to Arun" specification fixture.
"""

from __future__ import annotations

from pydantic import BaseModel


class AmbiguityCandidate(BaseModel):
    id: str
    label: str


class AmbiguityResolution(BaseModel):
    resolved: bool
    candidate: AmbiguityCandidate | None = None
    clarifying_question: str | None = None


def resolve_ambiguity(
    candidates: list[AmbiguityCandidate], target_description: str
) -> AmbiguityResolution:
    """Never guesses. docs/research/03-COMPETITOR-WEAKNESSES.md item 7."""
    if len(candidates) == 1:
        return AmbiguityResolution(resolved=True, candidate=candidates[0])
    if len(candidates) == 0:
        return AmbiguityResolution(
            resolved=False,
            clarifying_question=(
                f"I couldn't find anything matching '{target_description}'. "
                "Could you give me more detail?"
            ),
        )
    options = ", ".join(c.label for c in candidates)
    return AmbiguityResolution(
        resolved=False,
        clarifying_question=(
            f"I found multiple matches for '{target_description}': {options}. "
            "Which one did you mean?"
        ),
    )
