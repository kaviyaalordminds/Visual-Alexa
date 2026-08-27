"""STT-mishear clarification — brief acceptance test #8: "Open Rome"
spoken with borderline STT confidence should produce "Did you say
Chrome?" rather than either guessing Chrome outright or failing with no
explanation.

Pure text heuristics only: `extract_action_target` recognizes a small,
named set of "<verb> <target>" command shapes (never a general parser —
`IntentInterpreter` still does the real classification afterward, brief
§27); `find_closest_match` uses the standard library's `difflib` (no new
dependency — CLAUDE.md: "Never introduce a dependency where the standard
library ... already solves the problem") to compare the target against a
caller-supplied list of names that actually exist (e.g. registered
applications) — it only ever suggests a name that is real, never a
fabricated one, and only when confidence is high enough to be useful but
not so high that a real name is being second-guessed for no reason.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from voice.core.models import MishearSuggestion

_ACTION_TARGET_RE = re.compile(r"^(open|close|launch|start)\s+(.+?)[.!?]*$", re.IGNORECASE)

# Below this STT confidence, a target that doesn't exactly match a known
# name is worth double-checking; at or above it, the words are trusted
# as heard (a real name simply not being in `known_names` yet is not
# treated as a mishear).
_DEFAULT_CONFIDENCE_THRESHOLD = 0.85

# How close a target must be to a known name before it's worth asking
# about at all — below this, silence (nothing here resembles anything
# real) is more honest than a wild guess.
_DEFAULT_SIMILARITY_THRESHOLD = 0.72


def extract_action_target(text: str) -> tuple[str, str] | None:
    """Returns `(verb, target)` for a small set of action verbs this
    heuristic supports, or `None` if the utterance doesn't match that
    shape."""
    match = _ACTION_TARGET_RE.match(text.strip())
    if not match:
        return None
    return match.group(1).lower(), match.group(2).strip()


def find_closest_match(
    target: str, candidates: list[str], *, threshold: float = _DEFAULT_SIMILARITY_THRESHOLD
) -> str | None:
    """Pure function — no I/O. Never returns a candidate identical
    (case-insensitively) to `target`; that isn't a mishear."""
    if not target or not candidates:
        return None
    target_lower = target.strip().lower()
    best: tuple[float, str] | None = None
    for candidate in candidates:
        ratio = SequenceMatcher(None, target_lower, candidate.lower()).ratio()
        if ratio >= threshold and (best is None or ratio > best[0]):
            best = (ratio, candidate)
    if best is None or best[1].lower() == target_lower:
        return None
    return best[1]


def suggest_correction(
    text: str,
    known_names: list[str],
    *,
    confidence: float,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
) -> MishearSuggestion | None:
    """docs/phase-5 §112-ish (STT error handling). Pure function — no I/O,
    no model call. Returns `None` whenever there's nothing safe to
    suggest: confidence already high enough, the utterance isn't a
    recognized "<verb> <target>" shape, or nothing in `known_names` is a
    close-enough match."""
    if confidence >= confidence_threshold:
        return None
    parsed = extract_action_target(text)
    if parsed is None:
        return None
    verb, target = parsed
    match = find_closest_match(target, known_names, threshold=similarity_threshold)
    if match is None:
        return None
    return MishearSuggestion(corrected_text=f"{verb} {match}", suggested_target=match)
