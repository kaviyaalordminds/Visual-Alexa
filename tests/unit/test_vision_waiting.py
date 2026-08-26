"""docs/phase-3 §27 — future-compatible visual wait conditions. Same
cancellation discipline as computer_control.core.waiting: only suspension
point is asyncio.sleep."""

from __future__ import annotations

import asyncio

import pytest
from computer_control.core.models import Rect
from vision.core.models import GroundedElement, SceneGraph, SceneNode, TargetDescription, TextRegion
from vision.core.waiting import (
    wait_until_element_visible,
    wait_until_scene_changes,
    wait_until_text_present,
)


@pytest.mark.asyncio
async def test_wait_until_element_visible_succeeds_once_present():
    calls = {"n": 0}

    async def observe():
        calls["n"] += 1
        if calls["n"] < 2:
            return []
        return [GroundedElement(name="Save", text="Save", confidence_score=0.9, visible=True)]

    result = await wait_until_element_visible(
        observe, TargetDescription(text="Save"), timeout_seconds=1, poll_interval_seconds=0.01
    )
    assert result.satisfied is True


@pytest.mark.asyncio
async def test_wait_until_element_visible_times_out_honestly():
    async def observe():
        return []

    result = await wait_until_element_visible(
        observe, TargetDescription(text="Save"), timeout_seconds=0.05, poll_interval_seconds=0.01
    )
    assert result.satisfied is False
    assert result.detail is not None


@pytest.mark.asyncio
async def test_wait_until_text_present():
    tiny_bounds = Rect(left=0, top=0, width=1, height=1)

    async def observe_text():
        return [TextRegion(text="Download", confidence=0.9, bounds=tiny_bounds)]

    result = await wait_until_text_present(
        observe_text, "download", timeout_seconds=1, poll_interval_seconds=0.01
    )
    assert result.satisfied is True


@pytest.mark.asyncio
async def test_wait_is_cancellable():
    async def observe():
        return []

    task = asyncio.ensure_future(
        wait_until_element_visible(
            observe, TargetDescription(text="Save"), timeout_seconds=10, poll_interval_seconds=0.05
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_wait_until_scene_changes():
    baseline = SceneGraph(root=SceneNode(name="root", role="Window"))
    changed = SceneGraph(
        root=SceneNode(name="root", role="Window", children=[SceneNode(name="New", role="Text")])
    )
    calls = {"n": 0}

    async def capture():
        calls["n"] += 1
        return baseline if calls["n"] < 2 else changed

    result = await wait_until_scene_changes(
        capture, baseline, timeout_seconds=1, poll_interval_seconds=0.01
    )
    assert result.satisfied is True
