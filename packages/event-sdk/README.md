# Event SDK

Future typed client helpers for subscribing to VEYRA's event stream
(docs/architecture/12-EVENTS.md) from non-Python, non-TypeScript consumers,
or for a richer subscription API than the raw WebSocket the desktop shell
uses directly in Phase 1.

Phase 1's `EventBus` and WebSocket transport live in
`services/local-api/app/core/event_bus.py` and
`services/local-api/app/api/events.py`; this package is a placeholder for
a future dedicated client SDK.
