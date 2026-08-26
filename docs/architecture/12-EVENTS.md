# 12 — Event Architecture

## 1. Core types

```
Event
  id: str
  type: EventType
  payload: EventPayload      # typed per EventType
  correlation_id: str        # ties an event to a task/request chain
  timestamp: datetime

EventBus (interface)
  publish(event: Event) -> None
  subscribe(event_type: EventType, handler) -> Subscription
  unsubscribe(subscription: Subscription) -> None
```

Phase 1 implements `EventBus` as an in-process publisher plus a WebSocket
fan-out (`/events` — see `docs/api`) so the desktop shell can subscribe over
the same local connection it uses for REST calls. This is intentionally the
simplest implementation that satisfies the interface; a future phase may
swap in a message broker without changing any publisher/subscriber code,
because they depend only on the `EventBus` interface.

## 2. Event catalog (Phase 1: types defined and emitted where applicable)

```
assistant.listening
assistant.thinking
assistant.planning
assistant.executing
assistant.confirmation_required
assistant.completed
assistant.error
task.started
task.progress
task.completed
device.connected
device.disconnected
system.health_changed      # Phase 1 emits this — see /health
```

## 3. Consumers

- UI (status screen today; conversation UI, task monitor, avatar in future
  phases)
- Avatar state manager (future) — every avatar state in the product brief
  §16 state machine maps 1:1 to an `assistant.*` event.
- Logs / audit trail — every event with a `correlation_id` is discoverable
  alongside its `AuditLog` rows for the same correlation ID.
- Notifications (future).

## 4. Phase 1 scope

Delivered: `Event`/`EventType`/`EventBus` contracts, WebSocket transport,
and `system.health_changed` as a real, working emitted event. Not
delivered: `assistant.*`/`task.*` events firing from real behavior (no live
task runtime executes real work yet) — their payload shapes are defined and
unit-tested for serialization, not exercised end-to-end.
