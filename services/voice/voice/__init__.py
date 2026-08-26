"""veyra-voice — VEYRA's Phase 5 voice intelligence engine.

See docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md for the architecture.

This package is HEARING + SPEAKING only (brief §130): it turns audio into
a normalized transcript and turns a task outcome into spoken text. It
never interprets intent (that's Phase 4's `IntentInterpreter`) and never
executes anything — a voice command gains no permissions or capabilities
a typed command wouldn't already have (brief §131: "the voice interface
is NOT a security bypass").
"""

from __future__ import annotations
