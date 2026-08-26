"""SpeechNormalizer — cleans up a raw STT transcript before it becomes a
`Task.description`. docs/phase-5/LANGUAGE-DETECTION.md §23-26, brief §23.

Normalization only ever removes noise (filler words, stutters/repeats,
excess whitespace) or fixes a small set of known STT mishears for VEYRA's
own vocabulary (e.g. "Veera"/"Vera" -> "Veyra") — it must never invent an
entity that was not actually said (brief's own constraint). Anything it
isn't confident about it leaves untouched; `NormalizedCommand.corrections`
records exactly what changed, so nothing here is a silent rewrite.
"""

from __future__ import annotations

import re

from voice.core.models import NormalizedCommand

# Filler words removed as whole tokens only (word-boundary match) so they
# never eat part of a real word (e.g. "umbrella" must not lose "um").
_FILLER_WORDS: frozenset[str] = frozenset(
    {
        "um",
        "umm",
        "uh",
        "uhh",
        "er",
        "erm",
        "ah",
        "like",
        "you know",
        "i mean",
        "so yeah",
        "basically",
    }
)

# Known STT mishears of VEYRA's own wake word / name — narrow and specific,
# never a general spell-checker (that would risk inventing entities).
_KNOWN_MISHEARS: dict[str, str] = {
    "veera": "veyra",
    "vera": "veyra",
    "vira": "veyra",
    "vaira": "veyra",
}

# A leading wake phrase is a HEARING-layer artifact, not part of the
# command — "Hey Veyra, open Chrome" must reach IntentInterpreter as
# "open Chrome", the same text "open Chrome" alone would. Only ever
# strips VEYRA's own name at the very start of the utterance, never
# elsewhere in the sentence.
_WAKE_PHRASE_RE = re.compile(r"^(?:hey[,]?\s+)?veyra[,]?\s+", re.IGNORECASE)

# docs/phase-5/TANGLISH.md — the brief's own "<object> <verb> pannu/panni"
# word order ("Chrome open pannu.") reordered into the verb-first English
# phrasing IntentInterpreter's existing templates already understand
# ("open Chrome"). The negative lookahead keeps this to a single clause —
# a sentence with more than one "pannu"/"panni" clause is left untouched
# rather than risk garbling it (see docs/phase-5/TANGLISH.md §3).
_TANGLISH_VERB_PANNU_RE = re.compile(
    r"^((?:(?!\bpannu\b|\bpanni\b)[\s\S])+?)\s+"
    r"(open|close|search|play|send|delete|create|find)\s+"
    r"(?:pannu|panni)\w*[.!?]*$",
    re.IGNORECASE,
)


def _strip_fillers(text: str) -> tuple[str, bool]:
    words = text.split()
    kept = [w for w in words if w.strip(".,!?").lower() not in _FILLER_WORDS]
    return " ".join(kept), len(kept) != len(words)


def _collapse_repeats(text: str) -> tuple[str, bool]:
    """Removes immediate word-level stutters ("the the file" -> "the
    file"), case-insensitively, punctuation-insensitively. Never collapses
    a deliberate repeat further apart in the sentence."""
    words = text.split()
    if not words:
        return text, False
    kept = [words[0]]
    changed = False
    for word in words[1:]:
        prev_norm = kept[-1].strip(".,!?").lower()
        cur_norm = word.strip(".,!?").lower()
        if prev_norm and prev_norm == cur_norm:
            changed = True
            continue
        kept.append(word)
    return " ".join(kept), changed


def _fix_known_mishears(text: str) -> tuple[str, list[str]]:
    corrections: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        lower = token.lower()
        if lower in _KNOWN_MISHEARS:
            corrected = _KNOWN_MISHEARS[lower]
            corrections.append(f"{token!r} -> {corrected!r}")
            return corrected
        return token

    fixed = re.sub(r"[A-Za-z']+", replace, text)
    return fixed, corrections


def normalize_command(raw_text: str) -> NormalizedCommand:
    """docs/phase-5 §23. Pure function — no I/O, no language model."""
    corrections: list[str] = []

    text = raw_text.strip()
    text = re.sub(r"\s+", " ", text)

    without_fillers, fillers_removed = _strip_fillers(text)
    if fillers_removed:
        corrections.append("removed filler words")

    without_repeats, repeats_removed = _collapse_repeats(without_fillers)
    if repeats_removed:
        corrections.append("collapsed repeated words")

    fixed_text, mishear_corrections = _fix_known_mishears(without_repeats)
    corrections.extend(mishear_corrections)

    without_wake_phrase = _WAKE_PHRASE_RE.sub("", fixed_text)
    if without_wake_phrase != fixed_text:
        corrections.append("stripped wake phrase")

    reordered = _TANGLISH_VERB_PANNU_RE.sub(
        lambda m: f"{m.group(2)} {m.group(1)}", without_wake_phrase
    )
    if reordered != without_wake_phrase:
        corrections.append("reordered Tanglish verb+pannu/panni")

    normalized_text = re.sub(r"\s+", " ", reordered).strip()

    return NormalizedCommand(
        raw_text=raw_text, normalized_text=normalized_text, corrections=corrections
    )


class SpeechNormalizer:
    """Thin stateless wrapper around `normalize_command` — matches
    `LanguageDetector`'s injectable-object shape."""

    def normalize(self, raw_text: str) -> NormalizedCommand:
        return normalize_command(raw_text)
