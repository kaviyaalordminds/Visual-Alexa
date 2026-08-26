"""docs/phase-2 §13 — do not assume an element exists immediately; poll
with a bounded timeout, and cancellation interrupts it immediately (a real
asyncio.CancelledError, not a bespoke flag). Exercised against the fake
UI Automation backend so the *retry logic itself* is proven correct,
independent of any real OS.
"""

import asyncio

import pytest
from computer_control.core.models import UIElementInfo
from computer_control.core.selectors import UISelector
from computer_control.core.waiting import UIElementNotFoundError, wait_for_element
from computer_control.testing import FakeUIAutomationBackend


async def test_finds_an_element_that_is_present_immediately():
    backend = FakeUIAutomationBackend()
    backend.seed_element(UIElementInfo(automation_id="save-btn", name="Save"))
    element = await wait_for_element(backend, UISelector.by_automation_id("save-btn"))
    assert element.name == "Save"


async def test_polls_until_an_element_appears():
    backend = FakeUIAutomationBackend()
    backend.seed_element(
        UIElementInfo(automation_id="save-btn", name="Save"), appear_after_calls=3
    )
    element = await wait_for_element(
        backend,
        UISelector.by_automation_id("save-btn"),
        timeout_seconds=2.0,
        poll_interval_seconds=0.05,
    )
    assert element.name == "Save"


async def test_times_out_if_element_never_appears():
    backend = FakeUIAutomationBackend()
    with pytest.raises(UIElementNotFoundError):
        await wait_for_element(
            backend,
            UISelector.by_automation_id("does-not-exist"),
            timeout_seconds=0.2,
            poll_interval_seconds=0.05,
        )


async def test_cancellation_interrupts_the_wait_immediately():
    backend = FakeUIAutomationBackend()  # never seeded — would wait forever

    task = asyncio.create_task(
        wait_for_element(
            backend,
            UISelector.by_automation_id("never-appears"),
            timeout_seconds=30,
            poll_interval_seconds=1,
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
