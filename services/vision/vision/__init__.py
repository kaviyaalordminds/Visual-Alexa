"""veyra-vision — VEYRA's Phase 3 visual screen understanding engine.

See docs/phase-3/PHASE-3-IMPLEMENTATION-PLAN.md for the architecture and
docs/phase-3/VISUAL-PERCEPTION-ARCHITECTURE.md for the full pipeline.

This package is perception only: it turns raw screen/window/UI state into
structured, provenance-tagged observations. It never decides what to do
about what it sees, and it never executes an action — that boundary is
absolute (docs/phase-3 §35/§56; CLAUDE.md 'never give the LLM unrestricted
system access').
"""

from __future__ import annotations
