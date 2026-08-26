# Phase 3 Implementation Plan — Visual Screen Understanding Engine

Written before substantial implementation, per the Phase 3 brief §0. Records
what Phase 1/2 actually built (re-verified, not assumed), where Phase 3's
suggested design reuses vs. conflicts with it, and the technology choices
with rationale.

## 1. What Phase 1/2 actually implemented (repository inspection findings)

Re-inspected `CLAUDE.md`, `docs/architecture/*`, `docs/phase-2/*`, and the
actual code before writing a line of Phase 3:

- **Screen capture already exists**: `computer_control.screen.MssScreenBackend`
  (`services/computer-control/computer_control/screen.py`) — `capture_full`,
  `capture_window`, `capture_active_window`, all `mss`-based, PNG/base64,
  gated by `screen_observation.enabled` + `computer_control.enabled` +
  a `PermissionGrant`. **Phase 3 reuses this directly** rather than building
  a second capture path — it only adds `capture_region`, which
  `MssScreenBackend` doesn't have yet.
- **Window enumeration already exists**: `computer_control.core.backends.WindowBackend`
  + `computer_control.windows.windows_ctl.WindowsWindowBackend` (real,
  Windows-only) + `computer_control.testing.FakeWindowBackend` (fake, for
  tests) — `list_windows`, `find_window`, `get_window`, `get_active_window`,
  plus focus/minimize/maximize/restore/close. Registered as Phase 2 tools
  `window.*`. **Phase 3 reuses this for "active window"/"window metadata"
  perception (brief §6) rather than re-implementing window detection.**
- **UI element discovery already exists, but flat, not a tree**:
  `computer_control.core.backends.UIAutomationBackend` (`find_element`,
  `find_all`, `click_element`, `type_into_element`) +
  `computer_control.windows.ui_automation.WindowsUIAutomationBackend` +
  `computer_control.testing.FakeUIAutomationBackend`. `UIElementInfo`
  (`computer_control.core.models`) already has exactly the fields brief §7
  wants (automation_id, name, control_type, class_name, enabled, visible,
  bounds, supported_patterns) — it is missing only `children`/`parent`
  (Phase 2 never needed a tree, only single-element lookup). **Phase 3 adds
  tree-walking as a new backend capability
  (`UIAutomationBackend.get_tree`) rather than replacing the existing
  find/click/type methods**, and does the *normalization* into a
  platform-independent `SceneNode` tree in the new Phase 3 package (see §3),
  keeping `computer_control` itself free of the "generic scene graph"
  concept the brief's §8 wants kept normalized/independent.
- **`UISelector`, `wait_for_element`, `ActionResult`/`ActionStatus`/
  `VerificationOutcome` already exist** (`computer_control.core`) and
  already do exactly what brief §22/§26/§25 ask for grounding/waiting/
  verification results — Phase 3 reuses these types directly rather than
  inventing parallel ones. `GroundedElement` (§19) is new (fusion is new),
  but is built as a richer wrapper *around* `UIElementInfo`/`VisualRegion`,
  not a replacement for them.
- **Trust/provenance labeling already exists, partially**:
  `veyra_contracts.enums.ContentSource` (`USER`, `OBSERVED_CONTENT`,
  `SYSTEM`) was defined in Phase 1 specifically for prompt-injection
  defense (`docs/security/07-PROMPT-INJECTION.md`) but nothing consumes it
  yet — no live planner exists. **Phase 3 extends this enum** (additively)
  with the more granular labels brief §42 wants
  (`USER_INPUT`, `SYSTEM_STATE`, `UI_OBSERVATION`, `DOCUMENT_CONTENT`,
  `WEB_CONTENT`, `TOOL_RESULT`, `AI_OUTPUT`) rather than creating a second,
  parallel trust-label enum — see §5.
- **Audit redaction already exists**:
  `services/local-api/app/services/audit.py`'s `_SENSITIVE_KEYS`
  field-name redaction (`password`/`secret`/`token`/`otp`/`credential`).
  **Phase 3's `PrivacyRedactor` (brief §29) reuses this same field-name set
  as its baseline** rather than inventing a second redaction vocabulary,
  and extends it to also redact by UI-element privacy classification (a
  password *field*, not just a JSON key named "password").
- **The Tool Registry / Policy Engine / audit pipeline is unchanged since
  Phase 2** and is the only execution/registration path in the codebase —
  confirmed by re-reading `services/local-api/app/services/tool_execution.py`
  and `app/services/computer_control/support.py`. Phase 3 tools plug into
  the identical `callable_executor`/`platform_unsupported_executor`
  machinery Phase 2 built, adding nothing new to that layer except one
  extra gate (see §6).
- **Environment constraint, restated**: this build/test environment is
  still Linux, not Windows (`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md`
  §2 applies unchanged). **What's new and good news for Phase 3
  specifically**: `tesseract-ocr` (with both `eng` and `tam` language
  data) installs and runs for real in this container — OCR, unlike UI
  Automation, is **not** Windows-only, so Phase 3's OCR engine is fully
  real and fully tested here, not just reviewed-but-unverifiable code.
  Verified directly: `pytesseract.image_to_data` against a rendered Tamil
  string round-trips correctly (see the Phase 3 report for the exact
  output).

## 2. The central technical decision: what's genuinely testable here

Same discipline as Phase 2, sharper split:

| Capability | Platform | Verified here? |
|---|---|---|
| OCR (English + Tamil) | Cross-platform (`tesseract`) | **Yes — real, against real rendered text** |
| Screen capture, region capture, monitor enumeration | Cross-platform (`mss`) | **Yes — real, against a real Xvfb display** |
| Perception fusion, grounding, ambiguity, confidence scoring | Pure Python logic | **Yes — real, deterministic, no OS dependency at all** |
| SceneDiff, privacy classification, redaction, trust boundaries | Pure Python logic | **Yes — real** |
| `ObservationCoordinator` priority/short-circuit logic | Pure Python logic, backend-injected | **Yes — real, against fakes proving the *decision logic*** |
| UI tree walking (`get_tree`) | Windows-only (UIA) | Real, reviewed code; not runtime-verified (no Windows kernel here) |
| DPI-scaling query | Windows-only (`GetDpiForWindow`) | Real, reviewed code; not runtime-verified |
| Vision provider (cloud or local model) | N/A | **Not implemented at all in Phase 3** — abstraction only, see §4 |

This means Phase 3 is, if anything, **more** verifiable in this
environment than Phase 2 was: only the UI-tree-walking and DPI-query
backends are Windows-gated; OCR, capture, and the entire fusion/grounding/
privacy layer (arguably the most architecturally important part of this
phase) are real and tested.

## 3. Package placement: `services/vision`

Phase 1 already reserved this exact directory
(`services/vision/README.md`: "ScreenCapture, OCREngine,
VisualGroundingModel implementations... See docs/architecture/07-VISION.md.
No implementation in Phase 1.") — Phase 3 fills it in, rather than
inventing a new package name. Structure:

```
services/vision/                    # new installable package: veyra-vision
  vision/
    core/
      models.py        # ScreenObservation, TextRegion, VisualRegion,
                        #   SceneNode/SceneGraph, GroundedElement,
                        #   TargetDescription, SceneDiff, Monitor,
                        #   CoordinateSpace
      privacy.py         # PrivacyLevel enum, SecretDetector, PrivacyRedactor
      confidence.py        # ConfidenceBand thresholds, configurable
      fusion.py               # PerceptionFusion: merges UIA+OCR+vision
                        #   findings into GroundedElements
      grounding.py              # GroundingEngine: find_by_text/role/name/
                        #   semantics, ambiguity handling
      diff.py                     # SceneDiff computation
      waiting.py                    # wait_until_* conditions, built on
                        #   computer_control.core.waiting's pattern
      vision_provider.py              # VisionProvider Protocol +
                        #   NotConfiguredVisionProvider (no real provider
                        #   ships in Phase 3 — see §4)
    ocr/
      engine.py           # OCREngine (pytesseract-based, real,
                        #   cross-platform, English + Tamil)
    windows/
      ui_tree.py            # get_tree() — extends
                        #   computer_control.windows.ui_automation,
                        #   Windows-only, lazy-imported, same discipline
                        #   as Phase 2
      dpi.py                   # DPI/monitor-scaling query — Windows-only
    coordinator.py                # ObservationCoordinator — decides which
                        #   sources to run, short-circuits on confidence
    testing/
      fakes.py                     # fake vision provider, fake DPI
                        #   backend, synthetic observations for tests
```

`computer_control` (Phase 2) is a declared dependency of `vision`
(Phase 3) — capture, window, and UIA-element backends are consumed, not
re-implemented. Nothing in `computer_control` is rewritten; it gains one
additive method (`UIAutomationBackend.get_tree`,
`ScreenBackend.capture_region`) exactly where Phase 3 needs a capability
Phase 2 didn't.

## 4. Vision provider: abstraction only, no real provider (brief §15–17)

`vision.core.vision_provider.VisionProvider` is a `Protocol`
(`analyze_image`, `detect_elements`, `describe_scene`, `locate_target`).
Phase 3 ships exactly one implementation:
`NotConfiguredVisionProvider`, which always returns a structured
"vision unavailable" result rather than raising — mirroring the existing
`AI: NOT CONFIGURED` status pattern from Phase 1's system status screen.
No local model and no cloud provider is wired in. This is not a shortfall
against the brief — §15–17 ask for the *abstraction* and the *policy gate*
a future provider must pass through, not a shipped model; §57 explicitly
excludes "unrestricted cloud vision" from this phase. The
`ObservationCoordinator` (§9 below) is built so that with only
`NotConfiguredVisionProvider` active, UIA + OCR + metadata alone already
answer the large majority of the brief's own example questions (§1) —
vision is the last-resort tier, exercised only when both other sources are
unavailable or insufficient, exactly matching the priority order in §3.

## 5. `ContentSource` extension (brief §42, reusing Phase 1's enum)

`veyra_contracts.enums.ContentSource` gains, additively:
`USER_INPUT`, `SYSTEM_STATE`, `UI_OBSERVATION`, `DOCUMENT_CONTENT`,
`WEB_CONTENT`, `TOOL_RESULT`, `AI_OUTPUT`. `TRUSTED_CONTENT_SOURCES =
{USER, USER_INPUT, SYSTEM, SYSTEM_STATE}` is the one place "which sources
may authorize an action" is decided — everything else (including
`UI_OBSERVATION` and `WEB_CONTENT`) is untrusted by default, matching
brief §41/§42 exactly: screen text is always tagged `UI_OBSERVATION`, and
`UI_OBSERVATION ∉ TRUSTED_CONTENT_SOURCES` is a unit-testable fact, not a
convention.

## 6. Tool registration: reuse the Tool Registry, not new REST endpoints

Brief §45 suggests new endpoints (`POST /observations`, `POST /grounding`,
`POST /scene/diff`). Per `CLAUDE.md` ("one Tool Registry... never a second
execution path" — already the exact reasoning applied in
`docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md` §3 to reject a second
service), **Phase 3 exposes every new capability as a registered tool**
through the existing `/tools/{id}/invoke`, not as bespoke routes. This
keeps the brief's own §35/§56 AI-safety boundary trivially true: a future
planner's perception requests and action requests both go through the
identical Policy-Engine-gated path, with no special-cased "read-only
perception API" that bypasses it. New tools: `screen.capture_region`,
`screen.observe`, `ui.get_tree`, `ui.find_all`, `ocr.extract`,
`vision.analyze`, `vision.locate`, `scene.diff`, `target.ground`.
`screen.get_active_window` from the brief's §34 list is **not** registered
separately — `window.get_active` (Phase 2) already returns exactly this;
registering a second tool with the same behavior under a different name
would fragment, not clarify, the tool surface (same reasoning already
applied to `ui.wait_for`/`ui.find` in Phase 2). `scene.compare` similarly
is not a separate tool from `scene.diff` — one tool, brief's §24 data
model, documented once.

Risk tiers: every new tool is **SAFE** (read-only perception; nothing in
this phase moves a mouse or types a key — Phase 2 already owns action)
**except** `screen.capture_region` (MODERATE, mirrors the other
`screen.*` tools' tier and gating) and `vision.analyze`/`vision.locate`
when (in a future phase) a *cloud* provider is configured, which must be
SENSITIVE per brief §17's "user must know when visual information leaves
the PC" — moot in Phase 3 since no such provider ships, but the tier
policy is documented now so a future provider addition can't quietly ship
as SAFE.

## 7. Database: deliberately minimal, documented simplification

The brief lists `ScreenObservation`/`WindowObservation`/
`UIElementObservation`/`TextRegion`/`VisualRegion`/`SceneDiff`/
`GroundingResult` as "potential entities" (§44, explicitly hedged).
**Phase 3 does not add any of these as persisted tables.** Reasoning:

- Raw screenshots were never persisted even in Phase 2 (base64 stays in
  the HTTP response only) — extending that same discipline, *structured*
  observation metadata (still "what was on this user's screen, moment to
  moment") is kept ephemeral too: computed on demand, held in an in-memory
  TTL cache (`vision.coordinator`, brief §30), and returned directly in
  the tool result, which **already** flows into the existing `AuditLog`
  (Phase 1) — so grounding/observation results are auditable without a
  second, redundant persistence path.
- No consumer exists yet that would query historical observations (no
  live planner) — designing seven normalized tables against a consumer
  that doesn't exist risks locking in the wrong shape. Phase 4's planner,
  if and when it needs observation history, is better positioned to drive
  that schema than Phase 3 guessing at it.
- This is the same "don't add abstraction beyond what's needed" judgment
  already exercised in Phase 1 (memory writes deferred until a live agent
  exists to write them) and Phase 2 (Application Registry *was* persisted,
  because Phase 2 had an immediate, concrete consumer: `application.launch`
  resolving a name before every real launch).

If a future phase needs observation history, the `AuditLog` rows already
written by every Phase 3 tool call (correlation ID, tool ID, target,
result summary, timestamp) are the starting point, not a gap to fill
retroactively.

## 8. Documentation set for this phase

`docs/phase-3/{VISUAL-PERCEPTION-ARCHITECTURE,SCREEN-OBSERVATION,
WINDOW-PERCEPTION,UI-TREE,OCR,VISION-PROVIDER,SCENE-GRAPH,
PERCEPTION-FUSION,VISUAL-GROUNDING,CONFIDENCE,PRIVACY,REDACTION,
PROMPT-INJECTION,SCENE-DIFF,PERFORMANCE,SECURITY-TESTS,
PHASE-3-TEST-RESULTS}.md`, each stating plainly what was verified in this
environment (OCR, capture, fusion/grounding/privacy logic — most of the
phase) versus what is correct-but-Windows-only code (UI tree walking, DPI
query) pending real-hardware validation, exactly continuing Phase 2's
disclosure discipline.
