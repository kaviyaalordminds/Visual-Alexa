# Vision Service (`veyra-vision`)

ScreenCapture (extends Phase 2), OCREngine (real, tesseract-backed,
English + Tamil), perception fusion, visual grounding, scene diffing, and
privacy/redaction. See `docs/architecture/07-VISION.md` §6 and
`docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md`. Implemented in Phase 3;
no implementation in Phase 1/2 (this README's original placeholder text).
Vision-model grounding (`VisualGroundingModel`) is abstraction-only — see
`docs/phase-3/VISION-PROVIDER.md`.
