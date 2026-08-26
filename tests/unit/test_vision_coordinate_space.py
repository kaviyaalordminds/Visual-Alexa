"""docs/phase-3 §12 — 'never assume screen coordinates == physical
pixels.' Pure math, no OS dependency."""

from __future__ import annotations

from computer_control.core.models import Rect
from vision.core.models import CoordinateSpace


def test_logical_to_physical_scales_up_at_150_percent():
    space = CoordinateSpace(monitor_index=1, dpi_scale=1.5)
    logical = Rect(left=100, top=200, width=50, height=20)
    physical = space.logical_to_physical(logical)
    assert physical == Rect(left=150, top=300, width=75, height=30)


def test_physical_to_logical_is_the_inverse():
    space = CoordinateSpace(monitor_index=1, dpi_scale=2.0)
    physical = Rect(left=200, top=400, width=100, height=40)
    logical = space.physical_to_logical(physical)
    assert logical == Rect(left=100, top=200, width=50, height=20)


def test_round_trip_at_various_scales():
    for scale in (1.0, 1.25, 1.5, 2.0):
        space = CoordinateSpace(monitor_index=1, dpi_scale=scale)
        original = Rect(left=40, top=80, width=120, height=60)
        round_tripped = space.physical_to_logical(space.logical_to_physical(original))
        assert round_tripped == original


def test_default_scale_is_identity():
    space = CoordinateSpace(monitor_index=1)
    rect = Rect(left=10, top=20, width=30, height=40)
    assert space.logical_to_physical(rect) == rect
