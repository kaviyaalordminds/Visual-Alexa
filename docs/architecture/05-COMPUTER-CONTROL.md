# 05 — Computer Control Architecture

## 1. Evidence hierarchy

VEYRA must never default to screenshots + coordinates. Every UI-targeting
tool declares which evidence tiers it is allowed to use, in priority order:

```
1. Native application API / official SDK / documented protocol
2. Windows UI Automation (UIA)
3. Accessibility tree (MSAA / IAccessible2 fallback)
4. Application-specific integration (plugin/extension the app provides)
5. Browser DOM (via BrowserAgent, see 06-BROWSER-CONTROL.md)
6. OCR (text extraction from a screenshot)
7. Vision model (semantic grounding over a screenshot)
8. Coordinate-based mouse/keyboard interaction — LAST RESORT ONLY
```

A controller must attempt tiers in order and only fall to a lower tier when
a higher one is unavailable or fails; the tier actually used is recorded on
the `ToolResult.evidence_tier_used` field for every action, making the
evidence hierarchy auditable, not just aspirational (see
`docs/security/06-AUDIT-LOGGING.md`).

## 2. Controllers — implemented in Phase 2 as `computer_control.*` backends

```
ApplicationBackend   # launch, focus, close, enumerate running apps —
                     # computer_control.windows.applications (real,
                     # Windows-only) + computer_control.registry
                     # (the resolver: alias -> known app -> discovered
                     # executable, never an assumed path)
WindowBackend         # enumerate windows, focus/minimize/maximize/
                     # restore/close, get bounds/title —
                     # computer_control.windows.windows_ctl (real,
                     # Windows-only, pywinauto UIA backend + pywin32
                     # foreground-window detection)
FilesystemEngine       # search, metadata, open, create/copy/move/rename
                     # — computer_control.filesystem (cross-platform,
                     # verified in every environment). No delete method
                     # exists on the class at all (docs/phase-2 §7) —
                     # not "disabled," absent.
ProcessBackend           # read-only enumerate/inspect —
                     # computer_control.processes (psutil,
                     # cross-platform). No termination capability exists.
ScreenBackend              # capture + capture_region (gated behind
                     # screen_observation.enabled AND
                     # computer_control.enabled) —
                     # computer_control.screen (mss, cross-platform,
                     # verified against a real Xvfb display). OCR (Phase 3)
                     # is a separate component — vision.ocr.engine.OCREngine
                     # — consuming this backend's output, not part of it.
KeyboardBackend             # text entry via a mandatory, structurally
                     # enforced InputTarget, never global key injection
                     # — computer_control.windows.keyboard (real,
                     # Windows-only)
MouseBackend                  # UISelector-resolved actions only — no
                     # coordinate-only entry point exists anywhere in
                     # the Phase 2 tool surface —
                     # computer_control.windows.mouse (real,
                     # Windows-only)
UIAutomationBackend             # find/click/type against pywinauto's UIA
                     # backend, tier 2 of the hierarchy above —
                     # computer_control.windows.ui_automation
```

Each backend implements a `Protocol` interface
(`computer_control.core.backends`) consumed by specific `ToolExecutor`s
(see `04-TOOL-ARCHITECTURE.md` and `docs/phase-2/COMPUTER-CONTROL-DESIGN.md`)
— backends themselves are never exposed directly to the planner/LLM, and
every Windows-only backend fails with a structured `PLATFORM_NOT_SUPPORTED`
error on a non-Windows host rather than crashing (see
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §2 for why this repository's
own development/test environment cannot runtime-verify the Windows-only
paths, and what was verified instead).

## 3. Why this ordering

`docs/research/03-COMPETITOR-WEAKNESSES.md` items 3–6 document, with direct
citation to Anthropic's and OpenAI's own computer-use documentation, that
coordinate/screenshot grounding is fragile to UI/DPI/layout changes and
prone to hallucinated elements. Native/UIA/accessibility sources give
exact, typed element identity and state, eliminating an entire class of
failure that pure vision grounding cannot avoid.

## 4. Confidence and verification interplay

A `ToolResult` from a tier-1–5 (structured) source is treated as
inherently higher confidence than a tier-6–8 (OCR/vision/coordinate) result,
feeding directly into the confidence-aware execution policy in
`03-AI-ARCHITECTURE.md` §5. A CRITICAL-risk action grounded only at tier 7–8
should, by policy, require explicit visual confirmation from the user before
execution (product brief §14, "adaptive observation strategy").

## 5. Phase 1 + Phase 2 scope

Phase 1 delivered the evidence-tier enum, controller interfaces, and their
wiring into the `ToolResult`/verification contracts, with every
implementation a stub. **Phase 2** delivers real implementations for
tiers 1 (native API — filesystem, application/window control via Win32)
and 2 (UI Automation — `ui.*`/`mouse.*`/`keyboard.*`), with
`ToolResult.evidence_tier_used` now genuinely populated per call (not just
modeled) — verified end-to-end against a live server. **Phase 3**
(`docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md`) adds tier 6 (OCR, real —
`vision.ocr.engine.OCREngine`, `docs/phase-3/OCR.md`) and the tier 7
abstraction (`vision.core.vision_provider.VisionProvider`; only
`NotConfiguredVisionProvider` ships — `docs/phase-3/VISION-PROVIDER.md`),
plus a tree-walking extension to tier 2
(`UIAutomationBackend.get_tree` — `docs/phase-3/UI-TREE.md`). Tier 3
(accessibility-tree fallback beyond UIA), tier 4 (app-specific
integration), tier 5 (browser DOM), and tier 8 (coordinate fallback)
remain unimplemented — no tool through Phase 3 exposes a coordinate-only
entry point at all, a deliberate scope boundary carried forward from
Phase 2, not an oversight. See `docs/phase-2/WINDOWS-UI-AUTOMATION.md`,
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md`, and
`docs/phase-3/VISUAL-PERCEPTION-ARCHITECTURE.md`.
