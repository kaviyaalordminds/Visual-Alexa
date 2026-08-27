"""VoiceConfirmationParser — resolves a spoken reply to a confirmation
prompt. docs/phase-5/VOICE-SECURITY.md, brief §46-49.

`UNCLEAR` (including anything below the confidence floor) must never be
treated as `AFFIRM` — a caller (the conversation manager) is required to
re-prompt ("Please say yes or no.") rather than proceed. This is the one
hard security-relevant rule in this module; everything else is ordinary
phrase matching. Voice biometrics/speaker authentication are explicitly
out of scope here and everywhere in Phase 5 (brief §49) — this module only
classifies *what was said*, never *who* said it.
"""

from __future__ import annotations

import re

from voice.core.enums import ConfirmationDecision
from voice.core.models import ConfirmationResult

_AFFIRM_PHRASES: frozenset[str] = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "yup",
        "sure",
        "okay",
        "ok",
        "confirm",
        "confirmed",
        "correct",
        "do it",
        "go ahead",
        "please do",
        "affirmative",
        # docs/phase-5/BARGE-IN.md — the reply to "Say 'continue' when
        # you're ready" (a paused-task resume prompt, not a CRITICAL-
        # action authorization, but still gated by the same confidence
        # floor and exact-phrase matching).
        "continue",
        "resume",
        "keep going",
    }
)

_DENY_PHRASES: frozenset[str] = frozenset(
    {
        "no",
        "nope",
        "nah",
        "cancel",
        "don't",
        "dont",
        "stop",
        "negative",
        "no way",
        "don't do it",
        "dont do it",
    }
)

# Below this confidence, even an exact-match phrase is UNCLEAR — brief §48:
# "yeah... maybe" spoken with hesitation must never authorize a CRITICAL
# action just because the words happened to match.
_MIN_CONFIDENCE = 0.7

_DENY_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{re.escape(phrase)}\b")
    for phrase in sorted(_DENY_PHRASES, key=len, reverse=True)
)


def parse_confirmation(text: str, *, confidence: float = 1.0) -> ConfirmationResult:
    """docs/phase-5 §46-48. Pure function — no I/O, no model call.

    `confidence` is the STT confidence for this utterance (or a caller's
    own combined confidence signal); it is treated as a hard gate before
    phrase matching even runs.
    """
    if confidence < _MIN_CONFIDENCE:
        return ConfirmationResult(decision=ConfirmationDecision.UNCLEAR, confidence=confidence)

    normalized = text.strip().lower().rstrip(".!?")
    if not normalized:
        return ConfirmationResult(decision=ConfirmationDecision.UNCLEAR, confidence=confidence)

    if normalized in _AFFIRM_PHRASES:
        return ConfirmationResult(decision=ConfirmationDecision.AFFIRM, confidence=confidence)
    if normalized in _DENY_PHRASES:
        return ConfirmationResult(decision=ConfirmationDecision.DENY, confidence=confidence)

    # A denial embedded in a longer sentence ("Actually, don't open it")
    # still counts as DENY — brief's own live-correction scenario.
    # Deliberately asymmetric: this leniency exists ONLY for DENY, never
    # for AFFIRM. A false DENY just re-asks or cancels safely; a false
    # AFFIRM would authorize something. This is exactly why "yeah...
    # maybe" (which contains the bare word "yeah") must still resolve to
    # UNCLEAR rather than AFFIRM — the embedded-phrase leniency below is
    # never applied to the affirm list.
    if any(pattern.search(normalized) for pattern in _DENY_PHRASE_PATTERNS):
        return ConfirmationResult(decision=ConfirmationDecision.DENY, confidence=confidence)

    # Hedged/uncertain phrasing ("yeah... maybe", "i think so", "probably")
    # is deliberately never phrase-matched to AFFIRM at all — brief §48's
    # exact scenario.
    return ConfirmationResult(decision=ConfirmationDecision.UNCLEAR, confidence=confidence)


class VoiceConfirmationParser:
    """Thin stateless wrapper around `parse_confirmation`."""

    def parse(self, text: str, *, confidence: float = 1.0) -> ConfirmationResult:
        return parse_confirmation(text, confidence=confidence)
