"""Settings gates for the visual-perception tools. docs/phase-3/PRIVACY.md.

Reuses the exact same `screen_observation.enabled` gate
`app/services/computer_control/screen_tools.py` already checks before any
`screen.*` tool captures pixels — a Phase 3 tool that can itself capture
pixels (`screen.capture_region`, `screen.observe`, `target.ground`'s
OCR/vision fallback tiers) is gated by the identical setting rather than a
second, parallel one. Tools that only ever consume an already-captured
image (`ocr.extract`, `vision.analyze`, `vision.locate`) or that never
touch pixels at all (`ui.get_tree`, `ui.find_all`, `scene.diff`) are not
gated here — the gate applies at the point pixels are captured, not at
every tool that later consumes them.
"""

from __future__ import annotations

from app.services.computer_control.screen_tools import screen_observation_enabled

__all__ = ["screen_observation_enabled"]
