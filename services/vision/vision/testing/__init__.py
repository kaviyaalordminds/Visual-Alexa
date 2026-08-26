"""Fake perception backends (vision provider, DPI query, UI-tree
provider) — deterministic, no OS/model dependency, mirroring
computer_control.testing's fake-backend pattern. See
docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §2.
"""

from __future__ import annotations

from vision.testing.fakes import FakeDpiProvider, FakeUITreeProvider, FakeVisionProvider

__all__ = ["FakeDpiProvider", "FakeUITreeProvider", "FakeVisionProvider"]
