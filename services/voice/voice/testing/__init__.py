"""Deterministic mock providers (brief §97/§115) — no audio hardware, no
real model, no network. See docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §3.
"""

from __future__ import annotations

from voice.testing.mocks import (
    MockAudioInput,
    MockAudioOutput,
    MockSTT,
    MockTTS,
    MockVAD,
    MockWakeWord,
)

__all__ = [
    "MockAudioInput",
    "MockAudioOutput",
    "MockSTT",
    "MockTTS",
    "MockVAD",
    "MockWakeWord",
]
