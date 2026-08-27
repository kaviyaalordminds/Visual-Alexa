# Phase 8 — Browser & Web Intelligence Engine

Builds VEYRA's browser engine on top of Phase 1 (foundation), Phase 2
(computer-control), Phase 3 (visual perception), Phase 4 (AI brain / task
execution), Phase 5 (voice), Phase 6 (avatar), and Phase 7 (universal
tool/integration/plugin platform). Started on explicit instruction
("Start Phase 8") following CLAUDE.md's phase-discipline rule.

## 1. What this phase builds

A real, Playwright-driven browser automation engine registered as
ordinary tools through Phase 7's `ToolRegistry` — not a second execution
path, not a mock. `PlaywrightBrowserAdapter` launches genuine Chromium
(brief §167's technology guideline: prefer Playwright), verified against
both a local test website (`tests/fixtures/browser_test_site.py`, brief
§145) and the fake adapter's fast deterministic test suite.

Following brief §171/§176's explicit scope limits: this phase ships the
*architecture* for browsing the web safely, not every possible website
integration and not the categories the Stop Condition (§26 below)
excludes.

## 2. Package layout

```
services/local-api/app/services/browser/
├── adapter.py        BrowserAdapter protocol, PlaywrightBrowserAdapter
├── manager.py         BrowserManager, BrowserRegistry, BrowserSession,
│                       BrowserWindow, BrowserTab, BrowserState
├── observation.py     ObservationService, PageStateAnalyzer, ObservationCache
├── elements.py         BrowserElement scoring, ElementResolver/ElementFusionEngine
├── security.py         URLValidator, WebContentSanitizer, InstructionBoundary,
│                       SecretRedactor, BrowserActionGuard
├── downloads.py        DownloadManager
├── workflow.py         BrowserVerifier, BrowserWorkflowEngine
├── research.py         WebResearchAgent, SourceRanker, ContentExtractor,
│                       ComparisonEngine
├── extension_bridge.py ExtensionBridgeService (secure local bridge)
├── website_adapters.py Interface-only stubs (Gmail/WhatsApp/YouTube)
├── tools.py             Every browser.*/web.research ToolDefinition+Executor
├── register.py          Wires everything into the real ToolRegistry
└── testing.py           FakeBrowserAdapter (fast, deterministic test double)
```

`app/api/browser.py` adds three HTTP routes: `GET /browser/sessions`,
`GET /browser/downloads`, `POST /browser/extension/command`.

## 3. Development order followed (brief §170)

1. Repository analysis — mapped Phase 2 (`computer_control` mouse/keyboard
   already exists, but browser interaction stays inside Playwright's own
   page context rather than OS-level input), Phase 3 (`OCREngine` reused
   directly for the vision-fallback element-resolution tier), Phase 4
   (`RecoveryManager`/`ErrorCategory` extended, never duplicated), Phase 7
   (`ToolRegistry`/`PolicyEngine`/`execute_tool_call` — the one chokepoint,
   unchanged).
2. Contracts: `veyra_contracts/browser.py` (`BrowserSessionInfo`,
   `BrowserTabInfo`, `BrowserElementInfo`, `PageObservation`,
   `ResearchSource`, `ResearchResult`, `ExtensionCommandRequest`); new
   `ErrorCategory`/`AgentState`/`DomainTrustStatus` enum members
   (additive, mirrored in `packages/contracts/typescript`).
3. `BrowserAdapter` (the Chrome/Edge decoupling seam, brief §3-4) before
   anything else depended on it.
4. `BrowserManager`/session/tab bookkeeping.
5. Navigation, tab management.
6. `ObservationService` (DOM outline + interactive elements + visible
   text — never the raw DOM, brief §10).
7. `ElementResolver`/`ElementFusionEngine` (DOM > accessibility > OCR
   vision fallback > coordinate, brief §2's priority order).
8. `browser.*` tools, wired through the existing `ToolRegistry`.
9. `BrowserWorkflowEngine` (ACT→OBSERVE→VERIFY for one action) +
   Phase 4 `RecoveryManager` reuse (new browser `ErrorCategory` members
   classified into its existing category sets, not a second recovery
   engine — see `app/services/agent/recovery.py`).
10. `ExtensionBridgeService` (secure local bridge, no packaged extension
    ships).
11. `WebResearchAgent` (bounded PLAN→SEARCH→SELECT→OPEN→OBSERVE→EXTRACT→
    EVALUATE→COMPARE→SYNTHESIZE loop, one tool call, not a second agent
    framework).
12. Download/upload handling with the dangerous-extension flag.
13. Security tests, prompt-injection tests, real-Playwright end-to-end
    tests against the local test website.
14. Documentation (this set).

## 4. What's explicitly NOT delivered (brief §171)

- No real Gmail/WhatsApp/Spotify/YouTube integration — `website_adapters.py`
  ships interface-only stubs (`GmailAdapter`, `WhatsAppWebAdapter`,
  `YouTubeAdapter`), every method `raise NotImplementedError`, none
  imported by `main.py`, mirroring `future_adapters.py`'s established
  Phase 7 pattern exactly.
- No browser history/bookmarks tools (brief §67-68 says "future-ready
  architecture," not "ship now") — not built at all this phase, honestly
  absent rather than stubbed.
- No banking automation, no autonomous purchasing (brief §40-41) — every
  payment-page action requires fresh human confirmation
  (`PAYMENT_CONFIRMATION_REQUIRED`, never satisfiable by a stored grant
  the way `RiskLevel.CRITICAL` already isn't in Phase 1's Policy Engine).
- No CAPTCHA/OTP/2FA bypass of any kind — automation stops and asks the
  user (`CAPTCHA_DETECTED`/`OTP_REQUIRED`).
- No unrestricted browser control exposed to webpages — the extension
  bridge's command set is closed (`ALLOWED_COMMANDS`), no
  `execute_arbitrary_command` exists anywhere.
- No packaged VEYRA browser extension — the "Authenticated Local Bridge"
  half of brief §71's diagram is real and tested; the extension itself is
  out of scope.
- No real smart-home platform, no remote-PC control (brief §176's Stop
  Condition, restated verbatim from CLAUDE.md's own Phase 8+ boundary).

## 5. Stop Condition (brief §176)

Per the brief and CLAUDE.md: stop after Phase 8. Do not automatically
proceed to Phase 9. Do not build a full smart-home platform, unrestricted
remote-PC control, banking automation, autonomous purchasing, a
CAPTCHA/OTP/2FA bypass, unrestricted browser control, or a webpage's
direct access to browser automation, without an explicit instruction to
begin the next phase.

See `PHASE-8-TEST-RESULTS.md` for verification detail and the real bugs
this phase's own testing found (and fixed).
