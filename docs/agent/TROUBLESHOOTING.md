# Agent Troubleshooting (Phase 11)

Diagnostic commands for the orchestration/task-execution layer
specifically — see `docs/phase-10/PRODUCTION-RUNBOOK.md` for
process-level (start/stop/logs/database) troubleshooting, which this page
doesn't repeat.

## "My task says CAPABILITY_UNAVAILABLE"

1. Check `GET /tasks/{id}` — `failure_reason` names exactly which
   capability is missing and why (never a generic error).
2. Cross-check `docs/agent/ORCHESTRATION.md` and `docs/phase-4/PLANNER.md`
   §1 for the current list of real planning templates
   (`open_application`, `search_files`, `open_file`, `browser_task`) vs.
   honestly-unavailable goals (`send_file`, `control_device`,
   `remote_device_task`, `delete_files`).
3. If the request should have matched a real template but didn't, check
   `IntentInterpreter`'s classification first —
   `python -c "from app.services.agent.intent import IntentInterpreter; print(IntentInterpreter().interpret('your request here'))"`
   from `services/local-api` (with the venv active) shows exactly which
   goal/entities were extracted, with no task/DB/HTTP round-trip needed.

## "My task went to WAITING_USER when I expected it to fail or succeed"

- Check `result.clarifying_question` — if it mentions "replan", this is
  `RecoveryManager` correctly escalating after real replanning was
  attempted and still failed twice (once initially, once after the
  replan) — see `docs/agent/RECOVERY.md`. This is expected behavior when
  `max_replans` is small (e.g. voice's own `_VOICE_TASK_BUDGET`) and the
  underlying condition is genuinely not transient.
- If it lists file candidates, this is ordinary ambiguity resolution
  (`docs/phase-4/PLANNER.md`), unrelated to Phase 11.

## "My 'office folder' alias isn't resolving"

1. Confirm the alias actually exists: `GET /memory?category=WORKFLOW` —
   look for a row with `key` matching what you said (case-insensitive
   exact match only; "office folder" won't match "the office folder" or
   "my office directory").
2. Confirm `content.path` is a non-empty string — `_make_memory_lookup_fn`
   silently falls through to ordinary search if `content` isn't a dict or
   has no `path` key (this is deliberate — an alias record with malformed
   content degrades to the pre-Phase-11 search behavior, never a crash).
3. Confirm the memory row's `user_id` matches the task's user — aliases
   are per-user (`docs/architecture/09-MEMORY.md` §2, "user-controlled").

## "My browser_task request didn't do what I expected"

- `browser_task` only ever plans `browser.launch` (+ `browser.search` +
  `browser.get_page` when a web search is named — see
  `docs/agent/ORCHESTRATION.md` §5). A request implying a specific site
  interaction beyond a generic web search (e.g. "search YouTube for X and
  play the first result") is **not** preplanned — the `browser.launch`/
  `browser.get_page` steps still run, but no click/play step is invented.
  This is intentional, not a bug: preplanning an unobserved click target
  would mean guessing.
- Check `GET /tasks/{id}/steps` — if you see exactly `browser.launch` and
  `browser.get_page` with no `browser.search` in between, the web-search
  phrase wasn't recognized by `_WEB_SEARCH_QUERY_RE` (`search (the )?web
  (for )?...`) — rephrase using that shape, or drive the remaining steps
  (`browser.click`, `browser.find`, etc.) directly via `POST /tools/{id}/
  invoke`, which remains fully available even when the planner doesn't
  preplan them.

## "My request naming another device/computer got refused"

Expected — `docs/security/04-DEVICE-TRUST.md`'s local-only boundary is
absolute. `IntentInterpreter._REMOTE_DEVICE_RE` catches phrasing like "on
my other computer"/"on my phone"/"on another laptop" *before* any goal
classification and routes it to `CAPABILITY_UNAVAILABLE`, specifically so
a phrase like "open Chrome on my other computer" is never silently
executed as a *local* Chrome launch. If a legitimate local request is
being misclassified this way, check the exact phrasing against
`_REMOTE_DEVICE_RE` in `app/services/agent/intent.py` — it matches "on
(my|another) (other|another) (computer|pc|laptop|machine|desktop|device|
phone|tablet)", not e.g. "on my desktop [wallpaper]" (no "other"/"another"
qualifier, so it's correctly not remote-device phrasing).

## "REPLAN keeps producing the same plan and failing the same way"

Expected when the underlying condition genuinely isn't transient — the
deterministic templates are pure functions of their inputs
(`intent`/`search`/`memory_lookup`), so if none of those inputs changed
between attempts, the replanned plan is identical to the one that just
failed. This is why `RecoveryManager` still bounds `REPLAN` by
`max_replans` and ultimately escalates to `ASK_USER` — replanning is a
real recovery mechanism for a real transient-condition case, not a
substitute for diagnosing a permanent one (permanent categories like
`FILE_NOT_FOUND`/`APPLICATION_NOT_FOUND` route straight to `ABORT`, never
`REPLAN`, per `docs/phase-4/RECOVERY.md` §1).

## Where to look next

- `docs/agent/AGENT-ARCHITECTURE.md` — component map, what's real vs. out
  of scope.
- `docs/phase-4/PHASE-4-TEST-RESULTS.md` — historical acceptance-test
  results, updated with Phase 11 supersession notes where relevant.
- `docs/PHASE-11-COMPLETION-REPORT.md` — this phase's own final report,
  including known limitations.
