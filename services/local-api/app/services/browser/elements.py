"""ElementResolver / ElementScorer / ElementFusionEngine.
docs/phase-8/ELEMENT-RESOLUTION.md, docs/phase-8/DOM-ACCESSIBILITY-VISION-FUSION.md.

brief §2 priority order: structured browser state > DOM > accessibility >
semantic element info > visual screenshot analysis > coordinates. This
module implements exactly that chain for one operation, "find the element
the user means": DOM/ARIA text-and-role scoring first (`ElementScorer`),
an optional OCR-on-screenshot fallback when nothing scores well
(`_vision_fallback`), fused into one ranked, confidence-scored list
(`ElementFusionEngine`) that boosts a DOM candidate whose bounding box a
vision hit agrees with — never blind concatenation.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

from veyra_contracts import BrowserElementInfo, EvidenceTier

from app.services.browser.adapter import BrowserAdapter, RawElement

# brief §14 — below this, VEYRA must ask rather than guess.
MIN_CONFIDENCE = 0.45
# brief §14 — two candidates within this margin of each other are
# "ambiguous," not "the top one wins."
AMBIGUITY_MARGIN = 0.12


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t}


_ROLE_WORDS = {
    "button": {"button"},
    "link": {"a", "link"},
    "checkbox": {"checkbox"},
    "radio": {"radio"},
    "input": {"input", "textbox", "field"},
    "menu": {"menu", "menuitem"},
}


@dataclass(frozen=True)
class ScoredElement:
    raw: RawElement
    score: float
    reason: str


class ElementScorer:
    """Pure text/role/attribute scoring over one page's already-fetched
    `RawElement`s — no I/O, so trivially unit-testable."""

    def score(self, query: str, element: RawElement) -> ScoredElement:
        if not element.visible or not element.enabled:
            return ScoredElement(element, 0.0, "not visible/enabled")

        query_tokens = _tokenize(query)
        if not query_tokens:
            return ScoredElement(element, 0.0, "empty query")

        best = 0.0
        reason = "no match"

        candidates = {
            "text": element.text,
            "aria_label": element.aria_label,
            "placeholder": element.placeholder,
            "name": element.name,
        }
        for field_name, value in candidates.items():
            if not value:
                continue
            value_lower = value.strip().lower()
            query_lower = query.strip().lower()
            if value_lower == query_lower:
                return ScoredElement(element, 1.0, f"exact {field_name} match")
            value_tokens = _tokenize(value)
            if not value_tokens:
                continue
            overlap = len(query_tokens & value_tokens) / len(query_tokens)
            if query_lower in value_lower and overlap > 0:
                overlap = max(overlap, 0.75)
            if overlap > best:
                best = overlap
                reason = f"{field_name} token overlap ({overlap:.2f})"

        for role_word, matching_tags in _ROLE_WORDS.items():
            if role_word in query_tokens:
                tag_or_role = {(element.role or "").lower(), (element.tag or "").lower()}
                if tag_or_role & matching_tags:
                    best = min(1.0, best + 0.15)
                    reason += f" + role hint '{role_word}'"

        return ScoredElement(element, round(min(best, 1.0), 3), reason)


@dataclass(frozen=True)
class ElementResolution:
    candidates: list[BrowserElementInfo]
    best: BrowserElementInfo | None
    ambiguous: bool
    reason: str


def _to_info(
    raw: RawElement, *, confidence: float, tier: EvidenceTier, element_ref: str
) -> BrowserElementInfo:
    description_parts = [p for p in (raw.role, raw.text or raw.aria_label) if p]
    description = " ".join(description_parts) or raw.tag or "element"
    return BrowserElementInfo(
        element_id=element_ref,
        role=raw.role,
        tag=raw.tag,
        text=raw.text,
        aria_label=raw.aria_label,
        placeholder=raw.placeholder,
        name=raw.name,
        visible=raw.visible,
        enabled=raw.enabled,
        bounding_box=raw.bounding_box,
        selector=f'[data-veyra-ref="{raw.element_ref}"]'
        if tier == EvidenceTier.BROWSER_DOM
        else None,
        semantic_description=description,
        confidence=confidence,
        evidence_tier=tier,
    )


def _boxes_overlap(a: dict[str, float] | None, b: dict[str, float] | None) -> bool:
    if not a or not b:
        return False
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["width"], a["y"] + a["height"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]
    return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2


class ElementFusionEngine:
    """brief §59 — combines DOM candidates with an optional OCR-on-
    screenshot vision pass, boosting a DOM candidate's confidence when a
    vision hit's bounding box overlaps it (real agreement between two
    independent signals), rather than ever just concatenating lists."""

    def __init__(self, scorer: ElementScorer | None = None) -> None:
        self._scorer = scorer or ElementScorer()

    async def resolve(
        self,
        adapter: BrowserAdapter,
        tab_ref: str,
        query: str,
        *,
        ocr_engine=None,
    ) -> ElementResolution:
        raw_elements = await adapter.query_interactive_elements(tab_ref)
        dom_scored = [self._scorer.score(query, el) for el in raw_elements]
        dom_scored.sort(key=lambda s: s.score, reverse=True)

        vision_hits: list[tuple[float, dict[str, float]]] = []
        if ocr_engine is not None and (not dom_scored or dom_scored[0].score < MIN_CONFIDENCE):
            vision_hits = await self._vision_fallback(adapter, tab_ref, query, ocr_engine)

        candidates: list[BrowserElementInfo] = []
        for scored in dom_scored:
            if scored.score <= 0:
                continue
            confidence = scored.score
            for vscore, vbox in vision_hits:
                if _boxes_overlap(scored.raw.bounding_box, vbox):
                    confidence = min(1.0, confidence + 0.1 * vscore)
            candidates.append(
                _to_info(
                    scored.raw,
                    confidence=round(confidence, 3),
                    tier=EvidenceTier.BROWSER_DOM,
                    element_ref=scored.raw.element_ref,
                )
            )

        if not candidates and vision_hits:
            for i, (vscore, vbox) in enumerate(vision_hits):
                fake_raw = RawElement(
                    element_ref=f"vision-{i}",
                    role="text",
                    tag=None,
                    text=query,
                    aria_label=None,
                    placeholder=None,
                    name=None,
                    value=None,
                    visible=True,
                    enabled=True,
                    bounding_box=vbox,
                )
                cx = vbox["x"] + vbox["width"] / 2
                cy = vbox["y"] + vbox["height"] / 2
                candidates.append(
                    _to_info(
                        fake_raw,
                        confidence=round(vscore, 3),
                        tier=EvidenceTier.OCR,
                        element_ref=f"coord:{cx}:{cy}",
                    )
                )

        candidates.sort(key=lambda c: c.confidence, reverse=True)

        if not candidates or candidates[0].confidence < MIN_CONFIDENCE:
            return ElementResolution(
                candidates=candidates,
                best=None,
                ambiguous=False,
                reason=f"No candidate reached the minimum confidence ({MIN_CONFIDENCE}).",
            )

        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        ambiguous = (
            runner_up is not None and (top.confidence - runner_up.confidence) < AMBIGUITY_MARGIN
        )
        return ElementResolution(
            candidates=candidates,
            best=None if ambiguous else top,
            ambiguous=ambiguous,
            reason="Ambiguous — multiple close candidates." if ambiguous else "Resolved.",
        )

    async def _vision_fallback(
        self, adapter: BrowserAdapter, tab_ref: str, query: str, ocr_engine
    ) -> list[tuple[float, dict[str, float]]]:
        """brief §58 — screenshot fallback when DOM/accessibility cannot
        identify the target. Real OCR (tesseract via `vision.ocr.engine`)
        against the actual rendered page, never faked; honestly returns
        nothing when the OCR binary isn't available on this host, exactly
        like Phase 3's own OCR tools do."""
        try:
            png_b64 = await adapter.screenshot_png_base64(tab_ref)
            base64.b64decode(png_b64)  # fail fast on a malformed frame
            regions = ocr_engine.extract(png_b64, min_confidence=0.3)
        except Exception:
            # docs/phase-3/OCR.md's own precedent: an unavailable OCR
            # binary (or any other decode failure) means "no vision
            # fallback available," never a crash — the caller still has
            # the DOM-only candidate list.
            return []

        query_tokens = _tokenize(query)
        hits: list[tuple[float, dict[str, float]]] = []
        for region in regions:
            region_tokens = _tokenize(region.text)
            if not region_tokens or not query_tokens:
                continue
            overlap = len(query_tokens & region_tokens) / len(query_tokens)
            if overlap <= 0:
                continue
            score = overlap * region.confidence
            box = {
                "x": float(region.bounds.left),
                "y": float(region.bounds.top),
                "width": float(region.bounds.width),
                "height": float(region.bounds.height),
            }
            hits.append((score, box))
        hits.sort(key=lambda h: h[0], reverse=True)
        return hits[:5]
