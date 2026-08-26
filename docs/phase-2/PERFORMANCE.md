# Performance

## What's measured, and how

Every `ToolResult.duration_ms` is real, measured wall-clock time
(`time.monotonic()` around the executor call, `services/local-api/app/services/computer_control/support.py`) —
not a placeholder. It's returned in every API response and written into
every `AuditLog` row (`services/local-api/app/services/audit.py`), so
per-call latency is already inspectable end-to-end for any tool, matching
product brief §33's requirement without adding a separate metrics system
Phase 2 doesn't otherwise need.

## Observed latencies (this environment, manual verification)

| Operation | Observed | Notes |
|---|---|---|
| `filesystem.create_folder` | 1ms | Real filesystem write, temp-dir sandbox |
| `filesystem.create_file` | 0ms | |
| `filesystem.rename` | 0ms | |
| `filesystem.search` (empty directory) | 0ms | |
| `screen.capture` (640×480, Xvfb) | not separately isolated in manual testing; well under the tool's 30s timeout | Full round trip including PNG encoding |
| Policy Engine check (SAFE tool) | included in the above; no separate measurable overhead | In-process, no I/O beyond the tool itself |
| Policy Engine check (MODERATE, denied) | ~0ms | Single indexed DB query against `permission_grants` |

These numbers are from this container's filesystem/CPU, not representative
of Windows hardware — they demonstrate the instrumentation is real and the
overhead of the Policy Engine/audit-log wrapping is negligible relative to
the underlying operation, not a benchmark to hold Windows performance to.

## Timeouts (brief §25 — every operation bounded)

| Category | Default `timeout_seconds` | Where set |
|---|---|---|
| `application.*`, `window.*` | 30 (Phase 1 `ToolDefinition` default) | Not overridden — these are typically fast |
| `filesystem.*` | 30 | Explicit in `filesystem_tools.py._tool()` |
| `ui.*` | 15 | Explicit in `ui_tools.py._tool()`; `wait_for_element`'s own internal default is 5s, independently configurable per call via the `timeout_seconds` argument |
| `keyboard.*`, `mouse.*`, `screen.*` | 30 (default) | Fire-and-forget or single-shot; no long-running work to bound further |

No tool in Phase 2 has an unbounded timeout, and `wait_for_element`
(the one genuinely polling operation) always has both a timeout and a
poll interval — never a bare `while True`.

## Not blocking the event loop (brief §34)

Every `FilesystemEngine` method wraps its actual (synchronous) filesystem
I/O in `asyncio.to_thread(...)` (`computer_control/filesystem/engine.py`)
rather than calling `Path.mkdir()`/`shutil.copy2()` etc. directly on the
event loop — verified structurally (every `_*_sync` helper is invoked only
via `asyncio.to_thread`) and behaviorally (the FastAPI server continues
serving `/health` concurrently with a filesystem operation in progress,
consistent with every integration test in the suite completing without
serialization stalls). The real Windows backends
(`computer_control.windows.*`) are written as `async def` throughout;
`pywinauto` calls are themselves synchronous/blocking Win32 calls, so a
future hardening pass should wrap them in `asyncio.to_thread` the same way
the filesystem engine does — **not yet done, and called out here as a
known gap** rather than silently assumed handled (see Known Limitations
in the Phase 2 report).

## Execution-context isolation (brief §34)

Each tool call is a fully independent request/response cycle through
FastAPI/uvicorn's normal concurrency model — there is no shared mutable
state between concurrent tool calls beyond the database (which already
has its own per-request session scoping from Phase 1) and the
process-lifetime `ToolRegistry`/`ApplicationRegistry` singletons, which
are read-only after startup in Phase 2. Two concurrent calls (e.g. "type
into Notepad" and "focus Chrome") do not share any per-call mutable
object.
