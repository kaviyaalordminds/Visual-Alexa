"""Registers Phase 2's computer-control tools into the existing (Phase 1)
Tool Registry. See docs/phase-2/COMPUTER-CONTROL-DESIGN.md §3 for why
this lives inside the Local API process rather than as a separate
service, and docs/phase-2/PHASE-2-IMPLEMENTATION-PLAN.md §2 for the
platform-capability-gated backend selection every tool here goes through.
"""

from app.services.computer_control.register import register_computer_control_tools

__all__ = ["register_computer_control_tools"]
