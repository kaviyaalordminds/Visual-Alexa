"""resolve_followup — rewrites an ordinal/pronoun follow-up utterance into
concrete text before it becomes a `Task.description`. docs/phase-5/
CONVERSATION.md, brief §28-31.

This is *input preparation*, never intent interpretation (brief §27): the
rewritten text is still handed to the real, unmodified `IntentInterpreter`
afterward. When nothing here recognizes `text` as a follow-up, it returns
`None` and the caller submits `text` unchanged — this function must never
fabricate a target when it isn't reasonably confident which one was meant.
"""

from __future__ import annotations

import re

from voice.core.models import VoiceSession

_ORDINAL_WORDS: dict[str, int] = {
    "first": 1,
    "1st": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
    "fifth": 5,
    "5th": 5,
    "five": 5,
}

_ORDINAL_RE = re.compile(r"\b(\w+)\s+(?:one|option|choice)\b", re.IGNORECASE)
_NUMBER_OPTION_RE = re.compile(r"\b(?:number|option)\s+(\d+)\b", re.IGNORECASE)
_PRONOUN_RE = re.compile(r"\b(it|that|this one)\b", re.IGNORECASE)


def _substitute(text: str, span: tuple[int, int], replacement: str) -> str:
    start, end = span
    return f"{text[:start]}{replacement}{text[end:]}"


def resolve_followup(text: str, session: VoiceSession) -> str | None:
    """docs/phase-5 §29-30. Pure function — no I/O, no model call.

    Tries, in order: "number/option N", an ordinal word ("the second
    one"), then a bare pronoun ("it"/"that"/"this one") resolved against
    `session.last_candidates` (brief §29) or, failing that,
    `session.last_task_goal` (brief §30's plain-pronoun case). Returns
    `None` if none of these apply.
    """
    candidates = session.last_candidates

    number_match = _NUMBER_OPTION_RE.search(text)
    if number_match and candidates:
        index = int(number_match.group(1)) - 1
        if 0 <= index < len(candidates):
            return _substitute(text, number_match.span(), candidates[index].label)

    ordinal_match = _ORDINAL_RE.search(text)
    if ordinal_match and candidates:
        ordinal = _ORDINAL_WORDS.get(ordinal_match.group(1).lower())
        if ordinal is not None and 0 <= ordinal - 1 < len(candidates):
            return _substitute(text, ordinal_match.span(), candidates[ordinal - 1].label)

    pronoun_match = _PRONOUN_RE.search(text)
    if pronoun_match:
        referent: str | None = None
        if len(candidates) == 1:
            referent = candidates[0].label
        elif session.last_task_goal:
            referent = session.last_task_goal
        if referent:
            return _substitute(text, pronoun_match.span(), referent)

    return None
