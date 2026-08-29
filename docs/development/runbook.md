# Development Runbook

Day-to-day local development workflow. For production packaging,
startup ordering, log locations, and live-diagnosis of a packaged build,
see `docs/phase-10/PRODUCTION-RUNBOOK.md` — this document does not
duplicate that content.

## Starting the backend and frontend locally

```
scripts\dev-backend.bat          # Windows: starts the Local API on 127.0.0.1:8756
cd apps\desktop && npm run dev   # starts the Vite dev server for the desktop shell
```

On this Linux sandbox (no Windows sidecar), run the Local API directly:

```bash
cd services/local-api
uvicorn app.main:app --host 127.0.0.1 --port 8756
```

## Running the checks before pushing

**Python** (contracts + computer-control + vision + voice + local-api +
every test under `tests/`):

```bash
bash scripts/check-python.sh
```

Runs ruff, then mypy per-package, then the full pytest suite from the
repo root — this is the one command that mirrors what CI should run
(`CLAUDE.md` testing rules: no skipping/weakening a test to make this
pass green).

**TypeScript** (desktop shell + shared contracts):

```bash
cd apps/desktop
npx tsc -b        # typecheck
npx eslint .      # lint
npx vitest run    # unit/component tests
```

## Live, human-in-the-loop verification

1. Start the backend (above).
2. Start the desktop shell (`npm run dev` in `apps/desktop`).
3. Open the app — the status list at the top reflects real backend
   health (`GET /system`), never a hard-coded green state.
4. Use the **VEYRA Tasks** panel to type a request (e.g. "Create a
   folder called VEYRA-Test"), click **Run Task**, and watch live step
   progress. If the action needs confirmation, the real prompt from
   `ConfirmationManager.build_prompt` appears with working Allow/Deny
   controls — see `docs/security/permissions.md` and
   `docs/testing/e2e.md` for the specific scenarios this has been
   verified against.

## Common failure modes and what they mean

- **Status list shows `NOT CONFIGURED`/`NOT ENABLED`/`DEGRADED` for a
  subsystem**: this is the health check doing its job, not a bug — see
  the `details` reason string next to that row (`GET /system`'s
  `details` map). Never treat a red/yellow status row as something to
  "fix" by hard-coding it green; fix the actual underlying
  configuration or report the honest gap.
- **A task never leaves `WAITING_PERMISSION`**: expected for any
  `MODERATE`/`SENSITIVE`/`CRITICAL` action with no stored grant — call
  `POST /tasks/{id}/confirm` (or use the Task Panel's Allow/Deny
  buttons) rather than looking for a bypass.
- **`database is locked` during a test run**: a background `/run`/
  `/confirm`/`/resume` task from a previous test wasn't drained before
  the next test's fixture teardown — see the `_drain_background_tasks`
  helper in `tests/integration/test_agent_tasks_api.py` and
  `test_phase12_events.py` for the fix pattern; every new test that
  triggers a background task via the real API should drain it the same
  way before returning.

## No failure-hiding scripts

Nothing in `scripts/` swallows a non-zero exit code or retries a failing
check silently. If `check-python.sh` or the frontend checks fail, that
is the real signal — fix the underlying issue, don't wrap the command to
hide it (`CLAUDE.md` — "do not skip, disable, or weaken a test").
