# Browser Tools

Every `browser.*`/`download.*`/`web.research` tool (`tools.py`),
registered through the existing Phase 7 `ToolRegistry` exactly like every
other capability in this codebase (brief §7/§76). No second execution
path — every call goes through the exact same `ToolRegistry -> PolicyEngine
-> execute_tool_call -> AuditLog` chain (CLAUDE.md, docs/security/01-
SECURITY-ARCHITECTURE.md) as every other tool in the system.

## 1. `target` conventions

Two conventions, matching `BrowserManager`'s own split:

- **Session-scoped** (`browser.close`/`focus`/`new_tab`/`list_tabs`/
  `current_tab`/`find_tab`, `download.list`) — `target` is a session_id,
  or omitted for the active session.
- **Tab-scoped** (everything else) — `target` is a tab_id, or omitted for
  the active session's active tab, resolved via
  `BrowserManager.resolve_tab_target`.

## 2. Risk tiers (brief §39)

| Tier | Tools |
|---|---|
| SAFE | launch, close, focus, new_tab, close_tab, list_tabs, switch_tab, current_tab, find_tab, navigate, back, forward, reload, stop_loading, search, get_page, get_elements, extract_text, find, scroll, wait, clipboard_read, download.list/status/open_location |
| MODERATE | click, type, key_press, select, screenshot, download, fill_form, clipboard_write, web.research |
| SENSITIVE | upload_file (`ConfirmationPolicy.ALWAYS`) |

Reading/navigating is low risk (brief §39: "Reading: LOW RISK"); clicking/
typing/downloading needs a real `PermissionGrant` or fresh confirmation
(never satisfied for CRITICAL-tier actions, though nothing here is
CRITICAL — payment/purchase confirmation is enforced dynamically instead,
see `BROWSER-SECURITY.md` §4).

## 3. The full catalog

`browser.launch/close/focus` — session lifecycle. `browser.new_tab/
close_tab/list_tabs/switch_tab/current_tab/find_tab` — tab management
(brief §46-47; `find_tab` is a real semantic search over title/URL/domain
substrings, no embeddings invented for it). `browser.navigate/back/
forward/reload/stop_loading` — navigation, `URLValidator`-gated (see
`BROWSER-SECURITY.md`). `browser.search` — configurable search engine
(`google`/`bing`/`duckduckgo`, brief §9). `browser.get_page/get_elements/
extract_text/find` — read-only observation and element lookup.
`browser.click/type/key_press/select/scroll/wait` — the interaction
primitives, DOM/ARIA/vision-resolved (see `ELEMENT-RESOLUTION.md`).
`browser.screenshot` — real PNG capture. `browser.upload_file` — SENSITIVE,
resolves the target file input the same way click/type do.
`browser.download`/`download.list/status/open_location` — see
`DOWNLOADS.md`. `browser.fill_form` — refuses sensitive field labels
outright (see `BROWSER-SECURITY.md` §2). `browser.clipboard_read/write` —
read redacts secrets before returning. `web.research` — see
`WEB-RESEARCH.md`.

## 4. Avatar state wiring (brief §139/§164)

`browser.navigate` publishes `AgentState.BROWSING`, `browser.search`
publishes `SEARCHING`, `browser.extract_text` publishes `READING`, and
any CAPTCHA/OTP/payment stop condition publishes `BLOCKED` — all over the
same real `voice.ui_state.changed` event channel Phase 6 established as
*the* avatar-state broadcast (never voice-exclusive despite the wire
event name; see `app/services/voice/manager.py`'s own docstring for why
that channel is shared, not duplicated). Verified end-to-end against the
real `event_bus` in `tests/integration/test_browser_avatar_ui_state.py`.
The frontend (`apps/desktop/src/avatar/visuals.ts`) maps all four new
states to a distinct aura color/eye state/label — `BLOCKED` reuses the
"concerned" eye state and amber aura the CONFIRMING state already uses,
since both mean the same thing to the user: VEYRA is waiting on you.

## 5. Semantic scrolling and pagination (brief §77/§79-80)

`browser.scroll` accepts `direction`/`amount` today — a bounded,
single-shot scroll, not a blind "scroll 20 times" loop. Full semantic
"scroll until X appears" (brief §77's literal example) is left as a
planner-level composition of `browser.scroll` + `browser.get_page`/
`browser.find` in a loop bounded by the Task's own `TaskBudget`
(`max_steps`), rather than a bespoke scroll-until tool duplicating that
budget logic. Infinite-scroll/pagination-specific helpers (brief §79-80)
are not separately implemented this phase — the same
`scroll`+`get_page`/`find` composition covers them, and a future phase
can add a dedicated helper if real usage shows it's needed.
