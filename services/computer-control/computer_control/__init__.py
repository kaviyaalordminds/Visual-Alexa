"""VEYRA computer-control engine — Phase 2.

Platform-independent core (models, selectors, results, backend
interfaces) lives in `computer_control.core` and is importable and
testable on any host. Real OS backends live in `computer_control.windows`
and are Windows-only (imported lazily; see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md
§2 for why). `computer_control.testing` provides fake backends implementing
the same interfaces, used to test orchestration logic on any host.
"""
