"""Text-driven lip-sync approximation — docs/phase-6/LIP-SYNC.md.

There is no real TTS audio pipeline in this environment (no audio
hardware/library, `docs/phase-5/PHASE-5-TEST-RESULTS.md` §5), so there is
no real phoneme/amplitude timing to drive an avatar's mouth from. Rather
than fake a waveform-driven lip sync that doesn't exist, this module is a
deterministic, honestly-approximate alternative: it classifies each
character of the *actual* response text into one of a small set of
mouth-shape buckets (`VisemeShape`) and lays them out along a synthetic
timeline at a fixed speaking rate. It is real in the sense that it always
reflects the real text being spoken and always produces a genuine,
reproducible timeline — but it is not derived from real audio, and a
future real TTS backend should supersede it by supplying actual phoneme
timings through the same `VisemeFrame` shape (the avatar-rendering layer
only ever consumes `list[VisemeFrame]`, never this function directly).

Bucket scheme is a generic, simplified grouping by mouth shape (the kind
of thing described in any classic animation reference on lip sync), not
any single vendor's or product's proprietary viseme set.
"""

from __future__ import annotations

from voice.core.enums import VisemeShape
from voice.core.models import VisemeFrame

# Average adult speaking rate; used only to size the synthetic timeline,
# never claimed to be a physically measured value for this text.
_DEFAULT_CHARS_PER_MINUTE = 900
_MIN_UNIT_MS = 60
_MAX_UNIT_MS = 140
_WORD_GAP_MS = 70

_VOWEL_AI = frozenset("ai")
_VOWEL_E = frozenset("e")
_VOWEL_O = frozenset("o")
_VOWEL_U = frozenset("u")
_LABIAL_FV = frozenset("fv")
_LABIAL_MBP = frozenset("mbp")
_LATERAL_L = frozenset("l")
_ROUNDED_WQ = frozenset("wq")


def _shape_for_char(ch: str) -> VisemeShape:
    lower = ch.lower()
    if lower in _VOWEL_AI:
        return VisemeShape.AI
    if lower in _VOWEL_E:
        return VisemeShape.E
    if lower in _VOWEL_O:
        return VisemeShape.OH
    if lower in _VOWEL_U:
        return VisemeShape.U
    if lower in _LABIAL_FV:
        return VisemeShape.FV
    if lower in _LABIAL_MBP:
        return VisemeShape.MBP
    if lower in _LATERAL_L:
        return VisemeShape.L
    if lower in _ROUNDED_WQ:
        return VisemeShape.WQ
    return VisemeShape.ETC


def text_to_visemes(
    text: str, *, chars_per_minute: int = _DEFAULT_CHARS_PER_MINUTE
) -> list[VisemeFrame]:
    """Pure function — no I/O, no model call, deterministic (same `text`
    always produces the same timeline). Returns `[]` for empty/whitespace-
    only text (nothing to animate). Consecutive letters that fall in the
    same bucket are merged into one longer frame rather than emitting one
    frame per character, so the result reads as mouth-shape *holds*, not
    a per-letter flicker. Word boundaries always insert a short `REST`
    frame, whether or not two adjacent words start/end in the same
    bucket — a spoken pause is real regardless of the surrounding
    shapes."""
    unit_ms = max(_MIN_UNIT_MS, min(_MAX_UNIT_MS, round(60_000 / max(chars_per_minute, 1))))

    frames: list[VisemeFrame] = []
    cursor_ms = 0

    def _push(shape: VisemeShape, duration_ms: int) -> None:
        nonlocal cursor_ms
        if duration_ms <= 0:
            return
        frames.append(VisemeFrame(shape=shape, start_ms=cursor_ms, duration_ms=duration_ms))
        cursor_ms += duration_ms

    for word in text.split():
        letters = [ch for ch in word if ch.isalpha()]
        if not letters:
            continue
        current_shape: VisemeShape | None = None
        run_length = 0
        for ch in letters:
            shape = _shape_for_char(ch)
            if shape == current_shape:
                run_length += 1
                continue
            if current_shape is not None:
                _push(current_shape, run_length * unit_ms)
            current_shape = shape
            run_length = 1
        if current_shape is not None:
            _push(current_shape, run_length * unit_ms)
        _push(VisemeShape.REST, _WORD_GAP_MS)

    # Trailing REST from the last word's gap is not a mouth shape anyone
    # is holding — drop it so the timeline ends on the last real sound.
    if frames and frames[-1].shape == VisemeShape.REST:
        frames.pop()

    return frames
