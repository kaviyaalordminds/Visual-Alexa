"""wait_for_element: docs/phase-2 §13 — do not assume an element exists
immediately; poll with a bounded timeout and never silently act on the
wrong element. Backend-independent (works against the fake backend in
tests and the real Windows backend identically), and naturally
cancellable: this coroutine's only suspension point is `asyncio.sleep`,
so `task.cancel()` on the caller's task interrupts it immediately with
`asyncio.CancelledError` rather than needing a bespoke cancellation flag —
see docs/phase-2 §24.
"""

from __future__ import annotations

import asyncio
import time

from veyra_contracts import ErrorCategory

from computer_control.core.backends import UIAutomationBackend
from computer_control.core.models import UIElementInfo
from computer_control.core.selectors import UISelector

DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.25


class UIElementNotFoundError(LookupError):
    code = ErrorCategory.UI_NOT_FOUND

    def __init__(self, selector: UISelector, timeout_seconds: float) -> None:
        super().__init__(
            f"No element matching {selector.model_dump(exclude_none=True)} "
            f"found within {timeout_seconds}s."
        )


async def wait_for_element(
    backend: UIAutomationBackend,
    selector: UISelector,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> UIElementInfo:
    deadline = time.monotonic() + timeout_seconds
    while True:
        element = await backend.find_element(selector, timeout_seconds)
        if element is not None:
            return element
        if time.monotonic() >= deadline:
            raise UIElementNotFoundError(selector, timeout_seconds)
        await asyncio.sleep(poll_interval_seconds)
