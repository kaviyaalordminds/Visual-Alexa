"""InterruptionClassifier — classifies a barge-in utterance into one of
VEYRA's four interruption types. docs/phase-5/BARGE-IN.md, brief §11-14.

`matched=False` means "ordinary speech, not an interruption command" — a
caller (the conversation manager) only acts on `matched=True`, and even
then always stops TTS playback immediately regardless of which type it
resolves to (brief §13: barge-in must stop speech the instant the user
starts talking; classification decides what happens *next*, not whether to
stop).
"""

from __future__ import annotations

from voice.core.enums import InterruptionType
from voice.core.models import InterruptionResult

# Exact-phrase matches, brief §14's own six examples plus close variants.
_EXACT_PHRASE_TYPES: dict[str, InterruptionType] = {
    "stop": InterruptionType.STOP_SPEAKING,
    "stop talking": InterruptionType.STOP_SPEAKING,
    "stop speaking": InterruptionType.STOP_SPEAKING,
    "shut up": InterruptionType.STOP_SPEAKING,
    "that's enough": InterruptionType.STOP_SPEAKING,
    "thats enough": InterruptionType.STOP_SPEAKING,
    "cancel": InterruptionType.CANCEL_TASK,
    "cancel that": InterruptionType.CANCEL_TASK,
    "cancel it": InterruptionType.CANCEL_TASK,
    "never mind": InterruptionType.CANCEL_TASK,
    "nevermind": InterruptionType.CANCEL_TASK,
    "wait": InterruptionType.PAUSE_TASK,
    "wait a second": InterruptionType.PAUSE_TASK,
    "hold on": InterruptionType.PAUSE_TASK,
    "pause": InterruptionType.PAUSE_TASK,
    "goodbye": InterruptionType.END_SESSION,
    "bye": InterruptionType.END_SESSION,
    "exit": InterruptionType.END_SESSION,
    "end session": InterruptionType.END_SESSION,
    "that's all": InterruptionType.END_SESSION,
}

# Words that keep "stop <...>" about the speech itself, not a task target.
_SPEECH_TARGET_WORDS = frozenset({"talking", "speaking", "it", "that", "please", "now"})

_LEADING_WORD_TYPES: dict[str, InterruptionType] = {
    "cancel": InterruptionType.CANCEL_TASK,
    "wait": InterruptionType.PAUSE_TASK,
    "pause": InterruptionType.PAUSE_TASK,
}


def classify_interruption(text: str) -> InterruptionResult:
    """docs/phase-5 §14. Pure function — no I/O, no model call.

    Contextual disambiguation (brief §14's "Stop talking" vs. "Stop
    Chrome"): a bare "stop" (optionally followed only by speech-referring
    words like "talking") means STOP_SPEAKING; "stop" followed by anything
    that names a target ("Stop Chrome", "Stop the download") means
    CANCEL_TASK instead — the user is naming what to cancel, not asking
    VEYRA to be quiet.
    """
    normalized = text.strip().lower().rstrip(".!?")
    if not normalized:
        return InterruptionResult(matched=False)

    if normalized in _EXACT_PHRASE_TYPES:
        return InterruptionResult(
            matched=True,
            interruption_type=_EXACT_PHRASE_TYPES[normalized],
            matched_phrase=normalized,
        )

    words = normalized.split()

    if words[0] == "stop" and len(words) > 1:
        remainder = words[1:]
        if all(w in _SPEECH_TARGET_WORDS for w in remainder):
            interruption_type = InterruptionType.STOP_SPEAKING
        else:
            interruption_type = InterruptionType.CANCEL_TASK
        return InterruptionResult(
            matched=True, interruption_type=interruption_type, matched_phrase=normalized
        )

    if words[0] in _LEADING_WORD_TYPES:
        return InterruptionResult(
            matched=True, interruption_type=_LEADING_WORD_TYPES[words[0]], matched_phrase=normalized
        )

    if "never mind" in normalized or "nevermind" in normalized:
        return InterruptionResult(
            matched=True, interruption_type=InterruptionType.CANCEL_TASK, matched_phrase=normalized
        )

    return InterruptionResult(matched=False)


class InterruptionClassifier:
    """Thin stateless wrapper around `classify_interruption`."""

    def classify(self, text: str) -> InterruptionResult:
        return classify_interruption(text)
