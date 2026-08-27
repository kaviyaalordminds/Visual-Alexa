# Browser Architecture

Covers §166's `BrowserAdapter`/`BrowserSession`/`TabManagement`/
`PageObservation` doc split as one document — the four areas are small
enough, and interdependent enough, that splitting them cost more
cross-referencing than it saved.

## 1. The seam: `BrowserAdapter`

Brief §3-4: "Do NOT tightly couple the browser engine to Chrome... Create
`BrowserAdapter`." Every other module in `app/services/browser/` depends
only on the `BrowserAdapter` `Protocol` (`adapter.py`), never on
Playwright directly:

- `PlaywrightBrowserAdapter` — the real implementation. Chromium-first
  (brief §3's primary target); `channel="msedge"` is the one extension
  point for "Secondary architecture: Microsoft Edge" without any caller
  changing. `executable_path`/`extra_launch_args` are deployment-
  environment overrides (this dev sandbox's pre-installed Chromium sits
  at a revision the pip-installed `playwright` package doesn't
  auto-resolve, and needs `--no-sandbox` to run as root) — a normal
  Windows install leaves both `None` and lets Playwright resolve its own
  managed browser exactly as `playwright install` sets up.
- `FakeBrowserAdapter` (`testing.py`) — a second, deterministic
  implementation the fast unit/integration test suite uses, mirroring the
  `computer_control.testing`/`vision.testing` fake-backend precedent
  Phase 2/3 already established.

Firefox/WebKit (brief §3's "Future") means adding a third adapter, never
touching a caller — the interface is already general enough (`launch`,
`new_tab`, `navigate`, `query_interactive_elements`, `list_links`, ...).

## 2. `BrowserManager` / `BrowserSession` / `BrowserWindow` / `BrowserTab`

One process-wide `browser_manager` singleton (`manager.py`), the same
module-level-singleton pattern `tool_registry`/`integration_registry`/
`device_pairing_service` already established — a launched browser process
cannot outlive this process anyway (CLAUDE.md: the Local API is the only
process that can invoke a tool), so there is nothing here that needs a
second, DB-backed source of truth.

- `BrowserSession` — one launched browser process (one `BrowserAdapter`
  instance), a `BrowserWindow`, a dict of `BrowserTab`s, and an
  `active_tab_id`.
- `BrowserWindow` — a coarse grouping of tabs. Playwright's own model (one
  `BrowserContext`, many `Page`s) has no separate concept of distinct OS
  windows, so — documented honestly rather than faked — every tab in a
  session belongs to that session's single default window; a page the
  site itself opens (`window.open`, `target=_blank`) is still tracked as
  a new tab (`is_popup=True`, brief §53 "New Window Detection"), never
  silently dropped.
- `BrowserTab` — `tab_id`, `title`, `url`, `domain` (derived), `status`,
  `favicon`, `is_popup`.
- `BrowserState` — a plain string-constant lifecycle
  (`LAUNCHING`/`READY`/`CLOSED`/`CRASHED`), not a `veyra_contracts` enum,
  since it never crosses the service boundary (`BrowserSessionInfo`
  carries `connection_status` as a free string).

`BrowserManager` tracks one "active" session (set by `launch`/`focus`) as
the implicit target for a tool call that doesn't name one explicitly —
mirrors how a real desktop user has one foreground browser window even
while multiple profiles/sessions exist (brief §116 "Session Isolation").
`resolve_tab_target(target)` is the one place every tab-scoped tool
resolves a `ToolCallRequest.target`: when given, it names a tab_id and
the *owning* session is used (not necessarily the active one, so a
research workflow can act on a background tab); when omitted, falls back
to the active session's active tab.

Resource limits (brief §135): `max_sessions` (default 4), `max_tabs_per_session`
(default 12) — both real, enforced, raising `BrowserManagerError` ->
`ErrorCategory.RESOURCE_BUSY`.

## 3. Page observation

Brief §10: "Do NOT send the entire page blindly to an LLM."
`ObservationService.observe()` builds a compact `PageObservation`
(`veyra_contracts.browser.PageObservation`):

- `dom_summary` — a short indented outline (brief §11's `PAGE > Header >
  Search input` example), capped at 60 nodes.
- `interactive_elements` — up to 40 `BrowserElementInfo`s, never the full
  DOM.
- `visible_text_excerpt` — capped, sanitized text.
- `login_state`/`captcha_detected`/`otp_detected`/`payment_page_detected` —
  `PageStateAnalyzer`'s regex/keyword heuristics (brief §93: "Do not claim
  perfect... detection" — these are a real, useful first line, never a
  guarantee).
- `domain_trust` — always `UNKNOWN` today (brief §92: "do not
  automatically trust new domains" — no persisted allow-list exists yet;
  a future phase can add a real, user-editable trust store on the same
  field).

`ObservationCache` caches briefly (3s default), invalidated on navigation
(URL change) — the honest stand-in for "significant state change"
without a real DOM-mutation observer (brief §132).

## 4. `PLAN → ACT → OBSERVE → VERIFY` for one action

Brief §81-84: closed-loop control, never "plan everything once, execute
blindly." The PLAN/REPLAN half is Phase 4's `AgentOrchestrator`/
`RecoveryManager`, reused unchanged (see `ERROR-RECOVERY.md`).
`BrowserWorkflowEngine.execute_and_verify()` (`workflow.py`) owns the
ACT→OBSERVE→VERIFY half for one action: capture URL/title before, run the
action, capture URL/title after, report `state_changed` — real signal
`browser.click` attaches to its result (`output.state_changed`) rather
than assuming success. Real audit/timeline data (brief §142) already
comes for free from the `AuditLog` row every tool call writes
(`app/services/tool_execution.py`) — this class never duplicates that.
