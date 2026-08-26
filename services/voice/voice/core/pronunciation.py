"""PronunciationDictionary — rewrites known terms into phonetic-friendly
spellings before they reach a `SpeechSynthesisProvider`. docs/phase-5/TTS.md,
brief §37-41.

TTS engines routinely mispronounce brand names and acronyms (reading
"VEYRA" letter-by-letter, or running "GitHub" together as one word). This
is a narrow, explicit substitution table — never a general text rewrite —
so the transcript/response text stored and logged elsewhere stays exactly
what was generated; only the copy actually handed to TTS is adjusted.
"""

from __future__ import annotations

import re

_PRONUNCIATIONS: dict[str, str] = {
    "VEYRA": "Vay-rah",
    "VS Code": "V S Code",
    "GitHub": "Git Hub",
    "OpenAI": "Open A I",
    "Claude": "Clawd",
    "YouTube": "You Tube",
}

_TERM_RE = re.compile(
    "|".join(re.escape(term) for term in sorted(_PRONUNCIATIONS, key=len, reverse=True)),
    re.IGNORECASE,
)


def apply_pronunciations(text: str) -> str:
    """docs/phase-5 §37-41. Pure function — text substitution only, no
    audio/model call. Matching is case-insensitive, but the replacement
    always uses the dictionary's canonical spelling regardless of the
    input's casing — this text is for TTS synthesis only."""

    def replace(match: re.Match[str]) -> str:
        matched = match.group(0)
        for term, pronunciation in _PRONUNCIATIONS.items():
            if term.lower() == matched.lower():
                return pronunciation
        return matched  # pragma: no cover - unreachable, every match is a known term

    return _TERM_RE.sub(replace, text)


class PronunciationDictionary:
    """Thin stateless wrapper around `apply_pronunciations`."""

    def apply(self, text: str) -> str:
        return apply_pronunciations(text)
