# Intent Understanding

`IntentInterpreter` (`app/services/agent/intent.py`) — text →
`veyra_contracts.StructuredIntent`. Deterministic, rule-based, no LLM
call. See `PHASE-4-IMPLEMENTATION-PLAN.md` §4 for why this is Phase 4's
"real, no-model-needed" capability. Never executes anything — pure
classification.

## 1. Recognized goals

`open_application`, `open_file`, `search_files`, `delete_files`,
`send_file`, `control_device`, `browser_task` — a fixed, small vocabulary
matched by regex against the request text, with a keyword-based entity
extractor (`file_type`, `time_constraint`, `location`, `ordering`,
`recipient`, `power_state`) layered on top.

## 2. Ambiguity at the wording level vs. the entity level

"Open Notepad." → `open_application` (a bare name is a direct app
launch). "Open my project." → `open_file` (the possessive "my" signals a
personal-file lookup, not a known application name) — this is *not* where
the ambiguity in the brief's Final Acceptance Test #10 is resolved; that
happens later, when `TaskPlanner` searches and finds multiple candidates
(see `PLANNER.md`). `IntentInterpreter` only decides *which planning path*
to take, never how many files exist.

## 3. Four intent statuses

`UNDERSTOOD`, `AMBIGUOUS`, `MISSING_INFORMATION`, `UNSAFE` — matches
brief §10 exactly. `AMBIGUOUS`/`MISSING_INFORMATION` route straight to
`WAITING_USER` before planning ever starts. `UNSAFE` (see
`PROMPT-INJECTION.md`) still passes through `PLANNING` structurally (the
only legal exit from `PLANNING` is the authorization gate every real plan
uses) but is rejected there without ever calling `TaskPlanner`.

## 4. Verified

`tests/unit/test_agent_intent.py` — 15 tests, pure Python, covering every
brief-quoted example phrase (Notepad, latest PDF in Downloads, PDF
downloaded yesterday, delete all files in Downloads, send PDF to Arun,
turn on the AC, open my project) plus all four brief §92 adversarial
phrases and idempotency (interpreting the same text twice is identical —
no hidden state).
