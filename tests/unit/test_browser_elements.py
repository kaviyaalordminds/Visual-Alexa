"""ElementScorer / ElementFusionEngine. docs/phase-8/ELEMENT-RESOLUTION.md."""

from __future__ import annotations

from app.services.browser.adapter import RawElement
from app.services.browser.elements import ElementFusionEngine, ElementScorer
from app.services.browser.testing import FakeBrowserAdapter, FakePage
from computer_control.core.models import Rect
from vision.core.models import TextRegion


def _el(ref: str, **kwargs) -> RawElement:
    defaults = {
        "role": None,
        "tag": "button",
        "text": None,
        "aria_label": None,
        "placeholder": None,
        "name": None,
        "value": None,
        "visible": True,
        "enabled": True,
        "bounding_box": {"x": 0, "y": 0, "width": 50, "height": 20},
    }
    defaults.update(kwargs)
    return RawElement(element_ref=ref, **defaults)


def test_scorer_exact_text_match_is_confidence_one():
    scorer = ElementScorer()
    scored = scorer.score("Download", _el("1", text="Download"))
    assert scored.score == 1.0


def test_scorer_partial_overlap_is_lower_confidence():
    scorer = ElementScorer()
    scored = scorer.score("download report", _el("1", text="Download"))
    assert 0 < scored.score < 1.0


def test_scorer_invisible_element_scores_zero():
    scorer = ElementScorer()
    scored = scorer.score("Download", _el("1", text="Download", visible=False))
    assert scored.score == 0.0


def test_scorer_disabled_element_scores_zero():
    scorer = ElementScorer()
    scored = scorer.score("Download", _el("1", text="Download", enabled=False))
    assert scored.score == 0.0


def test_scorer_no_match_scores_zero():
    scorer = ElementScorer()
    scored = scorer.score("Download", _el("1", text="Unrelated text entirely"))
    assert scored.score == 0.0


async def test_fusion_resolves_unambiguous_dom_match():
    adapter = FakeBrowserAdapter()
    adapter.add_page(
        "https://x/", FakePage(elements=[_el("1", text="Download PDF"), _el("2", text="Cancel")])
    )
    tab_ref = await adapter.new_tab(url="https://x/")
    fusion = ElementFusionEngine()
    resolution = await fusion.resolve(adapter, tab_ref, "Download PDF")
    assert resolution.best is not None
    assert not resolution.ambiguous
    assert resolution.best.element_id == "1"


async def test_fusion_flags_ambiguous_when_two_elements_tie():
    adapter = FakeBrowserAdapter()
    adapter.add_page(
        "https://x/", FakePage(elements=[_el("1", text="Submit"), _el("2", text="Submit")])
    )
    tab_ref = await adapter.new_tab(url="https://x/")
    fusion = ElementFusionEngine()
    resolution = await fusion.resolve(adapter, tab_ref, "Submit")
    assert resolution.ambiguous
    assert resolution.best is None


async def test_fusion_returns_no_best_when_nothing_matches():
    adapter = FakeBrowserAdapter()
    adapter.add_page("https://x/", FakePage(elements=[_el("1", text="Cancel")]))
    tab_ref = await adapter.new_tab(url="https://x/")
    fusion = ElementFusionEngine()
    resolution = await fusion.resolve(adapter, tab_ref, "Download the invoice")
    assert resolution.best is None
    assert not resolution.ambiguous


async def test_fusion_falls_back_to_vision_when_dom_has_no_match():
    adapter = FakeBrowserAdapter()
    adapter.add_page("https://x/", FakePage(elements=[_el("1", text="Cancel")]))
    tab_ref = await adapter.new_tab(url="https://x/")
    fusion = ElementFusionEngine()

    class _FakeOCR:
        def extract(self, image_base64, *, min_confidence=0.0, languages=None):
            return [
                TextRegion(
                    text="Download",
                    confidence=0.9,
                    bounds=Rect(left=10, top=10, width=80, height=20),
                    language="eng",
                )
            ]

    resolution = await fusion.resolve(adapter, tab_ref, "Download", ocr_engine=_FakeOCR())
    assert resolution.best is not None
    assert resolution.best.element_id.startswith("coord:")


async def test_fusion_boosts_dom_confidence_when_vision_agrees():
    adapter = FakeBrowserAdapter()
    box = {"x": 10, "y": 10, "width": 80, "height": 20}
    query = "download the full report today"
    # token overlap with the query is 2/5 = 0.4, just under MIN_CONFIDENCE
    # (0.45) on its own, so the vision fallback tier engages.
    adapter.add_page(
        "https://x/", FakePage(elements=[_el("1", text="the report", bounding_box=box)])
    )
    tab_ref = await adapter.new_tab(url="https://x/")
    fusion = ElementFusionEngine()
    scorer_only = ElementScorer().score(query, _el("1", text="the report", bounding_box=box))
    assert scorer_only.score < 0.45

    class _FakeOCR:
        def extract(self, image_base64, *, min_confidence=0.0, languages=None):
            return [
                TextRegion(
                    text="Download the full report",
                    confidence=0.9,
                    bounds=Rect(left=10, top=10, width=80, height=20),  # overlaps the DOM box
                    language="eng",
                )
            ]

    resolution = await fusion.resolve(adapter, tab_ref, query, ocr_engine=_FakeOCR())
    assert resolution.best is not None
    assert resolution.best.evidence_tier.value == "BROWSER_DOM"
    assert resolution.best.confidence > scorer_only.score
