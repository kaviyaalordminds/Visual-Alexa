# OCR

## 1. Real, cross-platform, genuinely tested

Unlike UI Automation, OCR is **not** Windows-only. `vision.ocr.engine.OCREngine`
wraps `pytesseract.image_to_data` against the system `tesseract` binary
(installed in this environment: `tesseract-ocr`, `tesseract-ocr-eng`,
`tesseract-ocr-tam`). Every `OCREngine` test in
`tests/unit/test_ocr_engine.py` runs against real, rendered images — there
is no mocked OCR path anywhere in this codebase.

## 2. Supported languages

`SUPPORTED_LANGUAGES = ("eng", "tam")` — English and Tamil, matching the
brief's explicit requirement, extensible later by installing the matching
`tesseract-ocr-<lang>` package and adding the code to this tuple.
Requesting an unsupported language raises `ValueError` at construction or
call time rather than silently falling back to English. A caller may
combine languages per call (`languages=("eng","tam")` → tesseract
`eng+tam`), independent of the engine's default.

Verified for real in this session: rendering the Tamil string
"பதிவிறக்கம்" (Download) with a Noto Sans Tamil font and running
`pytesseract.image_to_string(img, lang="tam")` returns the correct text
(a trailing zero-width non-joiner artifact is cosmetic, not a recognition
error) — see `tests/unit/test_ocr_engine.py::test_tamil_ocr_round_trips_with_noto_font`
and `PHASE-3-TEST-RESULTS.md`.

## 3. "Do not assume OCR is always correct"

Every `TextRegion` carries tesseract's own per-word confidence (0.0-1.0,
normalized from tesseract's 0-100 scale; tesseract's -1 "no confidence"
rows for structural lines are dropped, never coerced into a fake 0.0).
Nothing in this codebase upgrades a low-confidence OCR read to a higher
tier — `PerceptionFusion` weights OCR results using `EvidenceTier.OCR`'s
base score (0.6, below every structured source; see `CONFIDENCE.md`), and
`ocr.extract`'s `min_confidence` argument lets a caller filter, never
silently substitute, low-confidence regions.

## 4. Tool: `ocr.extract`

SAFE risk tier, no `screen_observation.enabled` gate — it operates on an
already-captured `image_base64` the caller supplies (typically from a
prior `screen.capture`/`screen.capture_region` call, which *is* gated),
keeping the gate at the point pixels are captured rather than at every
tool that later consumes them.
