# Event System (Phase 11 — unchanged, re-verified)

The Task Event Stream is unchanged by Phase 11: `EventBus`
(`app/core/event_bus.py`) + the `/events` WebSocket remain the single
event system every part of this codebase publishes into — no second
stream was added for the orchestrator's new capabilities.
`docs/phase-9`/`docs/phase-10`'s reliability work (heartbeat, bounded
per-subscriber queues, graceful `close_all_websockets()` on shutdown)
applies to every event Phase 11's additions publish, unmodified.

## Events Phase 11's additions publish

All three are existing `EventType.TASK_*` members, published through the
same `event_bus.publish_type(...)` calls every other orchestrator code
path uses:

- **Real `REPLAN`**: `TASK_RECOVERY_STARTED` (already published on
  entering `_recover`) → `TASK_RECOVERY_COMPLETED` → `TASK_PLANNED` (the
  replan itself) → then whatever the new plan's own execution naturally
  publishes (`TASK_STEP_STARTED`/`TASK_STEP_COMPLETED`/`TASK_STEP_FAILED`,
  ultimately `TASK_COMPLETED`/`TASK_FAILED`/`TASK_CONFIRMATION_REQUIRED`).
  No new `EventType` was added — a replan is observable as an ordinary
  recovery-then-plan sequence, distinguishable from a first plan only by
  the preceding `TASK_RECOVERY_*` events.
- **`WorkflowMemory` alias resolution**: publishes nothing extra — it
  only changes which path a normal `filesystem.open` plan step targets;
  that step's own `TASK_STEP_STARTED`/`TASK_STEP_COMPLETED` events are
  unaffected.
- **`browser_task` planning**: publishes nothing extra beyond what
  Phase 8's browser tools already publish for their own state
  (`VOICE_UI_STATE_CHANGED` with `agent_state=BROWSING`/`SEARCHING` from
  `browser.navigate`/`browser.search` — unchanged, Phase 8 code, not
  touched this phase).

## No new subscriber, no new queue

Phase 11 did not add a new WebSocket endpoint, a new subscriber type, or
change bounded-queue behavior. `tests/integration/test_readiness_and_
shutdown.py` (Phase 10) and the existing `/events` integration tests
re-ran unmodified as part of this phase's full regression pass.
