# Phase 3 Test Results

Run in this environment (Linux container, `Xvfb :99` virtual display,
`tesseract-ocr` + `tesseract-ocr-eng` + `tesseract-ocr-tam` + Noto Tamil
fonts installed), 2026-08-26.

## 1. Summary

- **Full repository suite**: 207 passed, 0 failed, 0 skipped-without-reason.
- **New Phase 3 tests**: 75, all passing (58 unit, 10 integration, 7 security).
- **Lint**: `ruff check` clean across `services/local-api`,
  `services/computer-control`, `services/vision`,
  `packages/contracts/python`, `tests`.
- **Types**: `mypy` clean across all four Python packages
  (`veyra_contracts`: 10 files, `computer_control`: 25 files, `vision`: 19
  files, `app`: 58 files).

## 2. What was verified for real vs. reviewed-only

| Area | Status |
|---|---|
| OCR (English + Tamil) | **Real** — `pytesseract`/`tesseract` against real rendered images, including a genuine Tamil round-trip |
| Screen capture, `capture_region`, monitor enumeration | **Real** — `mss` against a live Xvfb display |
| Perception fusion, grounding, ambiguity, confidence | **Real** — pure Python, fully exercised |
| Scene diff, privacy classification, redaction, trust boundaries | **Real** — pure Python, fully exercised |
| `ObservationCoordinator` tier-escalation policy | **Real** — pure-function tests, and integration tests against `FakeUIAutomationBackend` |
| Full tool chain (Policy Engine → Executor → Audit) | **Real** — real FastAPI app, real SQLite DB, real HTTP calls via `httpx.AsyncClient` |
| UI tree walking (`get_tree`'s pywinauto calls) | Reviewed only — Windows-only, no Windows kernel in this container |
| DPI scale query (`GetDpiForWindow`) | Reviewed only — Windows-only |
| Vision provider | N/A — no real provider ships in Phase 3 |

## 3. Required test scenarios (brief §continuing Phase 2's numbering)

1. **Notepad observation** — not directly runnable (no Notepad on Linux);
   the equivalent path (`screen.observe` against the real Xvfb desktop) is
   covered by `test_vision_tools_api.py::test_screen_observe_real_capture_and_privacy_default`.
2. **Notepad UI inspection** — `ui.get_tree` correctly reports
   `PLATFORM_NOT_SUPPORTED` on this host
   (`test_vision_tools_api.py::test_ui_get_tree_platform_not_supported_on_this_host`);
   the tree-walking logic itself is exercised against
   `FakeUIAutomationBackend` in the grounding tests below.
3. **Typed-text observation** — covered structurally by OCR extraction
   tests; no live typed-text scenario possible without Windows input.
4. **Calculator observation + button detection** — represented by the
   seeded-UI-tree grounding tests (`test_target_ground_single_match_is_grounded`).
5. **Finding "7" / "Save"** — `test_target_ground_single_match_is_grounded`
   grounds "Save" from a seeded tree; the same code path handles any text.
6. **Ambiguous Download/Download PDF/Download Image** —
   `test_target_ground_ambiguous_via_seeded_ui_tree` — **passes**,
   `AMBIGUOUS_TARGET` with 3 candidates, `target: null`.
7. **OCR test with confidence** — `test_ocr_extract_real_text` (API) and
   `tests/unit/test_ocr_engine.py::test_extracts_real_english_text_with_confidence` —
   real confidence score returned (0.95 for the rendered "Download" test
   case).
8. **DPI test across 100/125/150/200%** — not runtime-verifiable (Windows
   API); `vision/windows/dpi.py` and `vision/core/models.CoordinateSpace`
   implement and unit-test the transform math independently of the
   Windows-only query itself is not covered — see Known Limitations.
9. **Multi-monitor test** — `ObservationCoordinator.get_monitor_layout`
   uses `mss`, which is cross-platform; this container's Xvfb exposes a
   single virtual display, so only single-monitor enumeration was
   exercised for real. The per-monitor `Monitor` model and index/bounds
   logic are reviewed and unit-testable but a genuine two-monitor
   assertion was not runnable here.
10. **Visual-change / `SceneDiff` test** — `tests/unit/test_vision_diff.py`
    (5 tests) — real, passing.
11. **Privacy/password-field test, no secret in logs** — Fourth Acceptance
    Test, **passes** — `test_phase3_privacy_redaction.py::test_password_field_classified_secret_via_grounding`.
12. **Cloud-disabled test, local perception still works** — **passes** —
    `test_vision_provider_not_configured_no_cloud_upload_possible` plus
    every grounding/observation test above running with only
    `NotConfiguredVisionProvider` active.

## 4. Five acceptance tests from the brief

1. **Final Acceptance Test** (ground Download among Search/Settings) —
   equivalent covered by `test_target_ground_single_match_is_grounded`
   (single clear match → `GROUNDED`, target/bounds/confidence/sources
   populated, nothing clicked).
2. **Second Acceptance Test** (ambiguous Download variants) — **passes**,
   see §3 item 6 above.
3. **Third Acceptance Test** (malicious on-screen text) — **passes**,
   `test_malicious_screen_text_via_ocr_is_returned_as_inert_data_only`.
4. **Fourth Acceptance Test** (password field) — **passes**, see §3 item 11.
5. **Fifth Acceptance Test** (two monitors, target on monitor 2) — not
   runnable in this single-virtual-display container; see Known
   Limitations.

## 5. Known limitations

- Every Windows-only code path (`WindowsUIAutomationBackend.get_tree`,
  `vision/windows/dpi.py`) is real, reviewed code that has not executed
  on an actual Windows kernel in this session — identical caveat to Phase
  2's Windows-only backends.
- Multi-monitor and DPI-scaling behavior could not be exercised against
  real hardware or a real per-monitor DPI query. The coordinate-transform
  math itself (`CoordinateSpace.logical_to_physical`/`physical_to_logical`)
  is unit-tested for real (`tests/unit/test_vision_coordinate_space.py`);
  what's unverified is only the Windows-only DPI *query* that would supply
  a real `dpi_scale` value to that transform on an actual scaled display.
- No real vision model exists to test `vision.analyze`/`vision.locate`'s
  actual detection quality — only the abstraction and its "not
  configured" fallback path are verified.
