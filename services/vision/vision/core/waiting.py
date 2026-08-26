"""Future-compatible visual wait conditions. docs/phase-3 §27.

Same discipline as computer_control.core.waiting (docs/phase-2 §13/§24):
each function's only suspension point is `asyncio.sleep`, so cancelling
the calling task interrupts the wait immediately via
`asyncio.CancelledError` rather than needing a bespoke cancellation flag.
Every function takes a bounded `timeout_seconds`/`poll_interval_seconds`
and returns a `WaitResult` — it never raises just because the condition
wasn't met within the timeout, matching docs/phase-2 §24's 'a timeout is a
result, not necessarily an error.'
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel

from vision.core.diff import compute_scene_diff
from vision.core.grounding import GroundingEngine
from vision.core.models import GroundedElement, SceneGraph, TargetDescription, TextRegion

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.25

T = TypeVar("T")


class WaitResult(BaseModel):
    satisfied: bool
    elapsed_seconds: float
    detail: str | None = None


async def _poll(
    predicate: Callable[[], Awaitable[bool]],
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    detail_on_timeout: str,
) -> WaitResult:
    start = time.monotonic()
    deadline = start + timeout_seconds
    while True:
        if await predicate():
            return WaitResult(satisfied=True, elapsed_seconds=time.monotonic() - start)
        if time.monotonic() >= deadline:
            return WaitResult(
                satisfied=False,
                elapsed_seconds=time.monotonic() - start,
                detail=detail_on_timeout,
            )
        await asyncio.sleep(poll_interval_seconds)


async def wait_until_element_visible(
    observe_elements: Callable[[], Awaitable[list[GroundedElement]]],
    target: TargetDescription,
    *,
    grounding: GroundingEngine | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> WaitResult:
    engine = grounding or GroundingEngine()

    async def _check() -> bool:
        result = engine.ground(target, await observe_elements())
        return result.status == "GROUNDED" and bool(result.target and result.target.visible)

    return await _poll(
        _check,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        detail_on_timeout="Element did not become visible within timeout.",
    )


async def wait_until_element_hidden(
    observe_elements: Callable[[], Awaitable[list[GroundedElement]]],
    target: TargetDescription,
    *,
    grounding: GroundingEngine | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> WaitResult:
    engine = grounding or GroundingEngine()

    async def _check() -> bool:
        result = engine.ground(target, await observe_elements())
        return result.status == "NOT_FOUND" or not bool(
            result.target and result.target.visible
        )

    return await _poll(
        _check,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        detail_on_timeout="Element was still visible after timeout.",
    )


async def wait_until_text_present(
    observe_text: Callable[[], Awaitable[list[TextRegion]]],
    text: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> WaitResult:
    needle = text.strip().lower()

    async def _check() -> bool:
        regions = await observe_text()
        return any(needle in region.text.lower() for region in regions)

    return await _poll(
        _check,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        detail_on_timeout=f"Text '{text}' did not appear within timeout.",
    )


async def wait_until_window_exists(
    find_window: Callable[[], Awaitable[object | None]],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> WaitResult:
    async def _check() -> bool:
        return (await find_window()) is not None

    return await _poll(
        _check,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        detail_on_timeout="Window did not appear within timeout.",
    )


async def wait_until_scene_changes(
    capture_scene: Callable[[], Awaitable[SceneGraph]],
    baseline: SceneGraph,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> WaitResult:
    async def _check() -> bool:
        current = await capture_scene()
        return compute_scene_diff(baseline, current).has_changes

    return await _poll(
        _check,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        detail_on_timeout="Scene did not change within timeout.",
    )


async def wait_until_application_state_changes(
    get_state: Callable[[], Awaitable[T]],
    baseline: T,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> WaitResult:
    async def _check() -> bool:
        return (await get_state()) != baseline

    return await _poll(
        _check,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        detail_on_timeout="Application state did not change within timeout.",
    )
