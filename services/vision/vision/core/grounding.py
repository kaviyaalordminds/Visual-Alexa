"""Visual grounding: `TargetDescription -> GroundingEngine -> GroundedElement`.
docs/phase-3/VISUAL-GROUNDING.md.

Mandatory ambiguity handling (docs/phase-3 §22, and the brief's Second
Acceptance Test): when more than one candidate is a plausible match and no
single one is clearly best, `ground()` returns `AMBIGUOUS_TARGET` with
every plausible candidate — it never guesses by picking the first or
highest-confidence match when the field is close.

Pure Python, no OS or vision-model dependency — genuinely tested here.
"""

from __future__ import annotations

from vision.core.models import GroundedElement, GroundingResult, TargetDescription
from vision.core.vision_provider import VisionProvider

# docs/phase-3 §22 — if the best and second-best candidate's confidence
# scores are within this margin, treat the target as ambiguous rather than
# silently picking the higher-scoring one.
_AMBIGUITY_MARGIN = 0.1


class GroundingEngine:
    def find_by_text(self, elements: list[GroundedElement], text: str) -> list[GroundedElement]:
        needle = text.strip().lower()
        return [
            e for e in elements if e.text and needle in e.text.lower()
        ] or [e for e in elements if e.name and needle in e.name.lower()]

    def find_by_role(self, elements: list[GroundedElement], role: str) -> list[GroundedElement]:
        needle = role.strip().lower()
        return [e for e in elements if e.role and e.role.lower() == needle]

    def find_by_name(self, elements: list[GroundedElement], name: str) -> list[GroundedElement]:
        needle = name.strip().lower()
        return [e for e in elements if e.name and e.name.lower() == needle]

    def find_by_semantics(
        self, elements: list[GroundedElement], description: str
    ) -> list[GroundedElement]:
        """docs/phase-3 §19/§22 — a deliberately simple, explainable
        keyword-overlap match, not a claim of real natural-language
        understanding (that would require a configured vision/language
        model, out of scope for Phase 3 — see
        docs/phase-3/VISION-PROVIDER.md)."""
        words = {w for w in description.lower().split() if len(w) > 2}
        if not words:
            return []
        scored: list[tuple[float, GroundedElement]] = []
        for element in elements:
            haystack = " ".join(filter(None, [element.name, element.role, element.text])).lower()
            hay_words = set(haystack.split())
            overlap = len(words & hay_words)
            if overlap:
                scored.append((overlap / len(words), element))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [element for _, element in scored]

    async def find_by_visual_similarity(
        self,
        target: TargetDescription,
        image_base64: str | None,
        vision_provider: VisionProvider,
    ) -> list[GroundedElement]:
        """Last-resort tier (docs/architecture/05-COMPUTER-CONTROL.md §1) —
        only produces results when a real `VisionProvider` is configured
        and an image is supplied; `NotConfiguredVisionProvider` (Phase 3's
        only shipped provider) always returns an empty list here."""
        if image_base64 is None:
            return []
        regions = await vision_provider.locate_target(image_base64, target)
        return [
            GroundedElement(
                name=region.label,
                role=region.region_type,
                bounds=region.bounds,
                confidence_score=region.confidence,
                sources=[region.source],
            )
            for region in regions
        ]

    def best_match(
        self, candidates: list[GroundedElement], *, margin: float = _AMBIGUITY_MARGIN
    ) -> GroundingResult:
        if not candidates:
            return GroundingResult(status="NOT_FOUND", reason="No matching element found.")
        ranked = sorted(candidates, key=lambda e: e.confidence_score, reverse=True)
        if len(ranked) == 1:
            return GroundingResult(status="GROUNDED", target=ranked[0])
        top, runner_up = ranked[0], ranked[1]
        if (top.confidence_score - runner_up.confidence_score) < margin:
            return GroundingResult(
                status="AMBIGUOUS_TARGET",
                candidates=ranked,
                reason=(
                    f"{len(ranked)} candidates matched with no clearly best "
                    "result — never guessing between them."
                ),
            )
        return GroundingResult(status="GROUNDED", target=top)

    def ground(
        self, target: TargetDescription, elements: list[GroundedElement]
    ) -> GroundingResult:
        """docs/phase-3 §22 — the main entry point: gathers candidates from
        every applicable finder for the fields set on `target`, dedupes,
        and defers the GROUNDED/AMBIGUOUS_TARGET/NOT_FOUND decision to
        `best_match`."""
        pool: dict[str, GroundedElement] = {}

        def _add_all(found: list[GroundedElement]) -> None:
            for element in found:
                pool[element.id] = element

        if target.name:
            _add_all(self.find_by_name(elements, target.name))
        if target.text:
            _add_all(self.find_by_text(elements, target.text))
        if target.role:
            role_matches = self.find_by_role(elements, target.role)
            if pool:
                # Role narrows an existing text/name match set rather than
                # being unioned in — "the Download button" should not also
                # match every other button on screen.
                pool = {eid: e for eid, e in pool.items() if e in role_matches}
            else:
                _add_all(role_matches)
        if target.semantic_description:
            _add_all(self.find_by_semantics(elements, target.semantic_description))

        if not pool and not any(
            [target.name, target.text, target.role, target.semantic_description]
        ):
            return GroundingResult(
                status="NOT_FOUND", reason="TargetDescription had no identifying criteria."
            )
        return self.best_match(list(pool.values()))
