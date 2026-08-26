"""Real Windows backends. Every module in this package imports its Windows-
only dependencies (pywinauto, pywin32) lazily, inside functions/methods,
never at module import time — so importing `computer_control.windows`
itself never fails on a non-Windows host, even though every backend class
here will raise or fail at first real use there.

**Not executable or testable in this development environment** (Linux —
see docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2). Each module states
this again in its own docstring so it is not lost when read in isolation.
The orchestration logic these backends plug into (Policy Engine, Tool
Registry, verification, error mapping) is fully tested against
`computer_control.testing`'s fake backends instead — see
docs/phase-2/PHASE-2-TEST-RESULTS.md for exactly what that does and does
not prove.
"""
