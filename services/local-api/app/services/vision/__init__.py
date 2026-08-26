"""Phase 3 visual-perception tools, wired into the same (Phase 1) Tool
Registry every other capability uses — see
docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md §6: no second execution path.
"""

from __future__ import annotations

from app.services.vision.register import register_vision_tools

__all__ = ["register_vision_tools"]
