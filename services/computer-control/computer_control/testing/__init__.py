"""Fake backends implementing the exact same Protocol interfaces as the
real Windows backends (computer_control.core.backends). Used by
services/local-api's test suite to verify the orchestration/security
logic — Tool Registry wiring, Policy Engine integration, verification
result shape, error mapping — without requiring Windows.
See docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2.
"""

from computer_control.testing.fake_backends import (
    FakeApplicationBackend,
    FakeUIAutomationBackend,
    FakeWindowBackend,
)

__all__ = [
    "FakeApplicationBackend",
    "FakeUIAutomationBackend",
    "FakeWindowBackend",
]
