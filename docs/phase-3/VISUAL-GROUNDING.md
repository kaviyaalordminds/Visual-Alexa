# Visual Grounding

`TargetDescription → GroundingEngine → GroundedElement`
(`vision/core/grounding.py`).

## 1. Finders

`find_by_text`, `find_by_role`, `find_by_name`, `find_by_semantics`
(keyword-overlap ranking — explicitly documented as *not* a claim of real
NLP), and `find_by_visual_similarity` (async, only produces results when a
real `VisionProvider` is configured and an image is supplied — see
`VISION-PROVIDER.md`). `ground()` is the main entry point: it gathers
candidates from every finder applicable to the fields set on the caller's
`TargetDescription`, dedupes by element id, and hands the pool to
`best_match`.

## 2. Mandatory ambiguity handling

`best_match` ranks candidates by `confidence_score`. If the top and
runner-up scores differ by less than `_AMBIGUITY_MARGIN` (0.1), the result
is `AMBIGUOUS_TARGET` with every plausible candidate returned and `target`
left `None` — **never** a guess at `candidates[0]`. This is the direct
implementation of the brief's Second Acceptance Test: "Download" /
"Download PDF" / "Download Image" all matching with equal confidence
returns `AMBIGUOUS_TARGET` with 3 candidates, verified both as a pure unit
test (`tests/unit/test_vision_grounding.py::test_ambiguous_download_variants_never_guessed`)
and end-to-end through the real API
(`tests/integration/test_vision_tools_api.py::test_target_ground_ambiguous_via_seeded_ui_tree`).

## 3. `target.ground` tool

SAFE risk tier, gated by `screen_observation.enabled` (its OCR/vision
fallback tiers can capture pixels). Internally:
`ObservationCoordinator.ground_target` tries UIA-only grounding first,
escalating to OCR then vision only when the cheaper tier's result is
`NOT_FOUND` — `GROUNDED` and `AMBIGUOUS_TARGET` both count as "already
answered" and stop escalation immediately (`decide_next_tier`,
`vision/coordinator.py`; see `VISUAL-PERCEPTION-ARCHITECTURE.md` §1). The
tool never clicks or otherwise acts on the result — see
`PROMPT-INJECTION.md` §3 for the AI-safety boundary this preserves.
