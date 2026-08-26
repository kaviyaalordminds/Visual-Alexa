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

## 2. Future controllers (interfaces defined now, Phase 1 = stubs only)

```
ApplicationController   # launch, focus, close, enumerate running apps
WindowController         # enumerate windows, move/resize/activate
FileController            # search, read metadata, move/copy/rename
                          # (never delete without CRITICAL-tier confirmation)
ProcessController         # enumerate/inspect processes (read-only in
                          # Phase 1+; no arbitrary process termination
                          # without CRITICAL confirmation)
ScreenController           # capture (only when explicitly enabled), OCR
KeyboardController         # text entry via structured target, not raw
                          # global key injection
MouseController             # last-resort coordinate actions only, gated
                          # behind the evidence hierarchy above
SystemController            # read-only system status/info in Phase 1
```

Each controller implements a narrow interface consumed by specific
`ToolExecutor`s (see `04-TOOL-ARCHITECTURE.md`) — controllers themselves are
never exposed directly to the planner/LLM.

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

## 5. Phase 1 scope

Delivered: the evidence-tier enum, controller interfaces, and their wiring
into the `ToolResult`/verification contracts. Not delivered: any concrete
controller implementation (all are `NotImplementedError` stubs) — real
Win32/UIA/OCR/vision integration is explicitly out of Phase 1 scope per the
brief §39.
