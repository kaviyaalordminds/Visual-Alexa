"""LanguageDetector — English / Tamil / Tanglish (code-mixed) detection.
docs/phase-5/LANGUAGE-DETECTION.md, brief §20-22.

A pure heuristic, not a model: Tamil native-script text is identified by
Unicode code points (Tamil block U+0B80-U+0BFF); Tanglish (romanized Tamil
mixed with English, e.g. "Chrome open pannu") is identified by a small
dictionary of common romanized-Tamil command words. This is exactly what
`docs/architecture/08-VOICE.md` §2 already flagged as an "unverified,
industry-wide open problem" for the general case — this heuristic is
deliberately narrow (command-oriented vocabulary only) and its accuracy is
only what `docs/phase-5/PHASE-5-TEST-RESULTS.md` actually measures against
the brief's own worked examples, never claimed beyond that.
"""

from __future__ import annotations

import re

from voice.core.enums import Language
from voice.core.models import LanguageDetectionResult

_TAMIL_SCRIPT_RANGE = (0x0B80, 0x0BFF)

# Common romanized-Tamil words used in spoken commands (brief §20/§87-96's
# own worked examples: "pannu", "panni", "la", ...). Not an exhaustive
# Tanglish vocabulary — see docs/phase-5/TANGLISH.md for known gaps.
_ROMANIZED_TAMIL_KEYWORDS: frozenset[str] = frozenset(
    {
        "pannu",
        "panni",
        "pannunga",
        "pannuga",
        "panra",
        "panren",
        "panradhu",
        "irukka",
        "iruku",
        "irukku",
        "irundhu",
        "venum",
        "venaam",
        "illa",
        "illai",
        "vidu",
        "vidunga",
        "kudu",
        "kudunga",
        "sollu",
        "sollunga",
        "paaru",
        "paarunga",
        "po",
        "poo",
        "poga",
        "vaa",
        "vaanga",
        "seiyanum",
        "seiyunga",
        "seyyu",
        "epdi",
        "eppadi",
        "enna",
        "yaaru",
        "nu",
        "nnu",
        "dhaan",
        "dhan",
        "la",
        "oda",
        "unga",
        "nga",
        "romba",
        "konjam",
        "ippo",
        "appuram",
        "ellam",
    }
)

_WORD_RE = re.compile(r"[A-Za-z']+")

# Below this ratio of Tamil-script characters (of all alphabetic
# characters), a string with some Tamil script is still native-script
# Tamil, not "mixed" — full native-script sentences may still contain a
# few Latin-script product names (e.g. "Chrome"), which shouldn't flip the
# whole utterance to UNKNOWN.
_TAMIL_SCRIPT_DOMINANT_RATIO = 0.5


def _tamil_script_ratio(text: str) -> float:
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return 0.0
    lo, hi = _TAMIL_SCRIPT_RANGE
    tamil_chars = sum(1 for c in alpha_chars if lo <= ord(c) <= hi)
    return tamil_chars / len(alpha_chars)


def detect_language(text: str) -> LanguageDetectionResult:
    """docs/phase-5 §21. Pure function — no I/O, no model call."""
    words = _WORD_RE.findall(text)
    tamil_script_ratio = _tamil_script_ratio(text)

    if tamil_script_ratio >= _TAMIL_SCRIPT_DOMINANT_RATIO:
        # Native-script Tamil. Latin-script words alongside it (product
        # names, English loanwords) still count as code-mixing.
        mixed = bool(words)
        confidence = min(1.0, 0.6 + tamil_script_ratio * 0.4)
        return LanguageDetectionResult(
            language=Language.TA, confidence=confidence, mixed_language=mixed
        )

    if not words:
        if tamil_script_ratio > 0.0:
            return LanguageDetectionResult(
                language=Language.TA, confidence=0.6, mixed_language=False
            )
        return LanguageDetectionResult(
            language=Language.UNKNOWN, confidence=0.0, mixed_language=False
        )

    lower_words = [w.lower() for w in words]
    tanglish_hits = sum(1 for w in lower_words if w in _ROMANIZED_TAMIL_KEYWORDS)
    tanglish_ratio = tanglish_hits / len(lower_words)

    if tanglish_hits == 0 and tamil_script_ratio == 0.0:
        return LanguageDetectionResult(language=Language.EN, confidence=0.9, mixed_language=False)

    # Any romanized-Tamil keyword (or a minority of native-script Tamil
    # characters) alongside ordinary Latin words is Tanglish code-mixing —
    # brief §20's exact scenario ("Chrome open pannu.").
    confidence = min(1.0, 0.5 + tanglish_ratio + tamil_script_ratio)
    return LanguageDetectionResult(
        language=Language.TA_EN, confidence=confidence, mixed_language=True
    )


class LanguageDetector:
    """Thin stateless wrapper around `detect_language` — exists so a
    caller can depend on an injectable object (matching every other
    Phase 5 component's shape) even though today's implementation has no
    state to inject."""

    def detect(self, text: str) -> LanguageDetectionResult:
        return detect_language(text)
