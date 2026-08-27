# Element Resolution / DOM-Accessibility-Vision Fusion

Covers §166's `ELEMENT-RESOLUTION.md` and
`DOM-ACCESSIBILITY-VISION-FUSION.md` together — one resolver, one fusion
pass, one document.

## 1. Priority order (brief §2)

1. Browser APIs / structured browser state
2. DOM
3. Accessibility tree
4. Semantic element information
5. Visual screenshot analysis
6. Coordinate-based mouse interaction

`ElementFusionEngine.resolve()` (`elements.py`) implements exactly this
chain for one operation — "find the element the user means":

1. **DOM/ARIA text-and-role scoring** (`ElementScorer`) — pure, I/O-free
   text/role/attribute matching over `query_interactive_elements()`'s
   already-fetched `RawElement`s. Exact text match scores 1.0; token
   overlap against text/aria-label/placeholder/name scores proportionally;
   a role-word hint ("button", "link", "checkbox"...) in the query adds a
   small boost when it matches the element's tag/role. Invisible or
   disabled elements always score 0 — never a candidate.
2. **OCR-on-screenshot vision fallback** — only engaged when the best DOM
   candidate scores below `MIN_CONFIDENCE` (0.45). Real tesseract OCR
   (Phase 3's own `vision.ocr.engine.OCREngine`, reused directly — not a
   second OCR implementation) against the actual rendered page screenshot.
   Honestly returns nothing when the OCR binary isn't available on this
   host, exactly like Phase 3's own OCR tools do (`OCRUnavailableError`
   caught, not surfaced as a crash).
3. **Fusion boost, not concatenation** — when a DOM candidate's bounding
   box overlaps an OCR hit's bounding box, the DOM candidate's confidence
   is boosted (real agreement between two independent signals), never
   just appended as a second, separate candidate. When *no* DOM candidate
   scored above 0 at all, a vision-only candidate is created instead,
   tagged `EvidenceTier.OCR`, with `element_id="coord:<x>:<y>"` (a
   coordinate marker `tools.py`'s click executor recognizes).
4. **Coordinate click** — the true last resort. The resolver itself never
   invents coordinates from nothing; a caller can always pass explicit
   `x`/`y` to `browser.click` directly (bypassing resolution entirely) —
   that's the one legitimate way to reach `EvidenceTier.COORDINATE`, and
   every fallback tier used is logged in the tool's own output
   (`evidence_tier`), per brief §15's "every fallback should be logged."

## 2. Ambiguity (brief §14)

`AMBIGUITY_MARGIN` (0.12): when the top two candidates' confidences are
within this margin of each other, the resolution is `ambiguous=True` and
`best=None` — VEYRA asks the user instead of guessing
(`ErrorCategory.AMBIGUOUS_TARGET`, `user_action_required=True`). Two
buttons both labeled "Submit" is the canonical test case
(`tests/unit/test_browser_elements.py::test_fusion_flags_ambiguous_when_two_elements_tie`,
`tests/integration/test_browser_tools_api.py::test_click_ambiguous_target_requires_clarification`,
and for real, against a real page, `tests/integration/
test_browser_real_playwright.py`).

## 3. Semantic identity, not `x=521 y=384` (brief §60)

Every `BrowserElementInfo` (`veyra_contracts.browser`) carries `role`,
`tag`, `text`, `aria_label`, `placeholder`, `name`, `visible`, `enabled`,
`bounding_box`, `selector`, and a `semantic_description` — "button:
Download PDF" is what a caller/log ever sees, not raw coordinates, even
when the underlying tier used happened to be coordinate-based.

## 4. What's not delivered

No cross-`iframe` element resolution (brief §61) — `query_interactive_elements`
runs against the main frame's DOM only; a form embedded in an `<iframe>`
(the local test site's `/iframe` page) loads and is observable as a page,
but its own interactive elements aren't currently enumerated separately.
Documented honestly rather than silently broken — a future phase can add
frame-aware traversal on the same `RawElement`/`BrowserElementInfo` shape.
