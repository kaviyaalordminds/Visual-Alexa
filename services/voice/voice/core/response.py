"""ResponseGenerator — turns a real `TaskOutcome` into a natural,
concise, English/Tamil/Tanglish spoken response. docs/phase-5/TTS.md,
brief §32-41/§74-79.

The one hard rule (brief §77): VEYRA must never say "Done" when Phase 4
reports FAILED, and must never claim a `CAPABILITY_UNAVAILABLE` task
succeeded — `generate_response` only ever reads `outcome.state`/
`outcome.error`, it never assumes success. Tamil and Tanglish phrasings
here are direct, non-native-reviewed translations of the same English
templates — this is exactly the "no accuracy claimed without actual
testing" caveat `docs/phase-5/PHASE-5-TEST-RESULTS.md` must record; they
are a genuine best effort, not a verified-natural Tamil voice.
"""

from __future__ import annotations

from veyra_contracts import ErrorCategory, TaskState

from voice.core.enums import Language
from voice.core.models import TaskOutcome, VoiceResponse

# TaskStates that mean "nothing new to say yet" — the conversation manager
# decides separately whether an interim acknowledgement is warranted.
# WAITING_PERMISSION is deliberately not here: it always has a real
# `confirmation_prompt` to speak (brief §46, acceptance test §123).
_IN_PROGRESS_STATES: frozenset[TaskState] = frozenset(
    {
        TaskState.RECEIVED,
        TaskState.UNDERSTANDING,
        TaskState.PLANNING,
        TaskState.EXECUTING,
        TaskState.OBSERVING,
        TaskState.VERIFYING,
        TaskState.RECOVERING,
    }
)


def cancelled_text(language: Language = Language.EN) -> str:
    """Public alias of `_cancelled_text` for callers outside this module
    (e.g. barge-in's CANCEL_TASK handling) that need the same phrasing
    generate_response uses for a CANCELLED TaskOutcome."""
    return _cancelled_text(language)


def did_you_say_text(name: str, language: Language = Language.EN) -> str:
    """docs/phase-5 §112 — spoken when `suggest_correction` finds a
    close-but-not-exact match for a low-confidence "<verb> <target>"
    utterance (brief acceptance test #8, "Did you say Chrome?")."""
    if language == Language.TA:
        return f"{name} சொன்னீர்களா?"
    if language == Language.TA_EN:
        return f"{name} nu sonninga?"
    return f"Did you say {name}?"


def never_mind_text(language: Language = Language.EN) -> str:
    """Spoken when the user declines a "Did you say X?" clarification."""
    if language == Language.TA:
        return "சரி, பரவாயில்லை."
    if language == Language.TA_EN:
        return "Okay, never mind."
    return "Okay, never mind."


def goodbye_text(language: Language = Language.EN) -> str:
    """docs/phase-5 §14 — spoken when an END_SESSION interruption
    ("Goodbye", "Exit") closes a voice session."""
    if language == Language.TA:
        return "சரி, போய் வருகிறேன்."
    if language == Language.TA_EN:
        return "Okay, bye pòitu varen."
    return "Goodbye."


def ask_yes_no_text(language: Language = Language.EN) -> str:
    """docs/phase-5 §48 — the exact re-prompt VEYRA must use when a
    confirmation reply was UNCLEAR (never treated as authorization)."""
    if language == Language.TA:
        return "தயவுசெய்து ஆம் அல்லது இல்லை என்று சொல்லுங்கள்."
    if language == Language.TA_EN:
        return "Please yes nu illa no nu sollunga."
    return "Please say yes or no."


def _capability_unavailable_text(language: Language) -> str:
    if language == Language.TA:
        return "என்னால் அதைச் செய்ய முடியாது."
    if language == Language.TA_EN:
        return "Sorry, adhu enakku panna mudiyadhu — that capability illa."
    return "I can't do that — I don't have that capability yet."


def _completed_text(outcome: TaskOutcome, language: Language) -> str:
    # When result_summary is set it is the verbatim spoken response (e.g. a
    # conversational reply or a query answer) — speak it directly without
    # wrapping it in "Done. X is done." which would be nonsensical for
    # "It's 3:15 PM on Tuesday" or "Hello! I'm VEYRA...".
    if outcome.result_summary:
        return outcome.result_summary
    subject = outcome.goal
    if language == Language.TA:
        return f"முடிந்தது. {subject} தயார்." if subject else "முடிந்தது."
    if language == Language.TA_EN:
        return f"Done pannitten. {subject} ready." if subject else "Done pannitten."
    return f"Done. {subject} is ready." if subject else "Done."


def _failed_text(outcome: TaskOutcome, language: Language) -> str:
    if outcome.error is not None and outcome.error.code == ErrorCategory.CAPABILITY_UNAVAILABLE:
        return _capability_unavailable_text(language)
    message = outcome.error.message if outcome.error is not None else None
    if language == Language.TA:
        return f"முடியவில்லை. {message}" if message else "முடியவில்லை."
    if language == Language.TA_EN:
        return f"Sorry, mudiyala. {message}" if message else "Sorry, mudiyala."
    return f"I couldn't do that. {message}" if message else "I couldn't do that."


def _cancelled_text(language: Language) -> str:
    if language == Language.TA:
        return "சரி, ரத்து செய்தேன்."
    if language == Language.TA_EN:
        return "Okay, cancel pannitten."
    return "Okay, cancelled."


def _paused_text(language: Language) -> str:
    """docs/phase-5/BARGE-IN.md — spoken when a real PAUSE_TASK
    interruption actually pauses the underlying task (brief §14)."""
    if language == Language.TA:
        return "சரி, நிறுத்தி வைத்தேன். தொடரவா?"
    if language == Language.TA_EN:
        return "Okay, pause pannitten. Continue pannava?"
    return "Okay, I've paused. Say 'continue' when you're ready."


def _timed_out_text(language: Language) -> str:
    if language == Language.TA:
        return "அதிக நேரம் ஆனதால் நிறுத்திவிட்டேன்."
    if language == Language.TA_EN:
        return "Konjam time aachu, so stop pannitten."
    return "That took too long, so I stopped."


def _ambiguous_text(outcome: TaskOutcome, language: Language) -> str:
    # Speak Phase 4's own real question verbatim when it produced one —
    # never re-derive or paraphrase it (brief §74-79's "no false claims"
    # rule applies just as much to inventing wording as to inventing
    # outcomes). Only fall back to building a sentence from `candidates`
    # when no question text is available at all.
    if outcome.clarifying_question:
        return outcome.clarifying_question
    if not outcome.candidates:
        if language == Language.TA:
            return "இன்னும் கொஞ்சம் விவரம் சொல்ல முடியுமா?"
        if language == Language.TA_EN:
            return "Konjam more detail sollunga?"
        return "Could you tell me more about what you'd like me to do?"
    labels = ", ".join(c.label for c in outcome.candidates)
    n = len(outcome.candidates)
    if language == Language.TA:
        return f"{n} பொருந்தும் விருப்பங்கள் கிடைத்தன்: {labels}. எதை சொன்னீர்கள்?"
    if language == Language.TA_EN:
        return f"{n} matches kidaichuchu: {labels}. Edhu venum?"
    return f"I found {n} matches: {labels}. Which one did you mean?"


def generate_response(outcome: TaskOutcome, *, language: Language = Language.EN) -> VoiceResponse:
    """docs/phase-5 §74-79. Pure function — no I/O, no model call.

    `language` selects which of VEYRA's canned phrasings to use; it is not
    a translation service — text it has no explicit template for falls
    back to the EN branch of that template, never to silence.
    """
    if outcome.state == TaskState.COMPLETED:
        return VoiceResponse(
            text=_completed_text(outcome, language), language=language, should_speak=True
        )
    if outcome.state == TaskState.FAILED:
        return VoiceResponse(
            text=_failed_text(outcome, language), language=language, should_speak=True
        )
    if outcome.state == TaskState.CANCELLED:
        return VoiceResponse(text=_cancelled_text(language), language=language, should_speak=True)
    if outcome.state == TaskState.TIMED_OUT:
        return VoiceResponse(text=_timed_out_text(language), language=language, should_speak=True)
    if outcome.state == TaskState.WAITING_USER:
        return VoiceResponse(
            text=_ambiguous_text(outcome, language), language=language, should_speak=True
        )
    if outcome.state == TaskState.WAITING_PERMISSION:
        # Speak Phase 4's own ConfirmationManager-built prompt verbatim —
        # brief §46/§119's exact target/risk/reason phrasing, never a
        # voice-layer rewrite of it.
        text = outcome.confirmation_prompt or ""
        return VoiceResponse(text=text, language=language, should_speak=bool(text))
    if outcome.state == TaskState.PAUSED:
        return VoiceResponse(text=_paused_text(language), language=language, should_speak=True)
    if outcome.state in _IN_PROGRESS_STATES:
        return VoiceResponse(text="", language=language, should_speak=False)
    # Any other state not explicitly handled above — nothing safe to
    # fabricate.
    return VoiceResponse(text="", language=language, should_speak=False)


class ResponseGenerator:
    """Thin stateless wrapper around `generate_response`."""

    def generate(self, outcome: TaskOutcome, *, language: Language = Language.EN) -> VoiceResponse:
        return generate_response(outcome, language=language)
