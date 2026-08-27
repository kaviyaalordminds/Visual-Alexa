"""Voice-specific enums. Kept in this package, not `veyra_contracts` —
nothing outside the voice pipeline needs these shapes yet, the same
reasoning Phase 3 applied to keeping `PrivacyLevel` in `vision.core.privacy`
(docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §6).
"""

from __future__ import annotations

from enum import StrEnum


class VoiceState(StrEnum):
    """docs/phase-5 §12 (session status) and §43 (state machine) describe
    the same set of states from two angles — unified into one enum here
    rather than two near-duplicates that could drift apart.
    `VoiceSession.status` and `VoiceStateMachine`'s current state are the
    same field."""

    IDLE = "IDLE"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    UNDERSTANDING = "UNDERSTANDING"
    EXECUTING = "EXECUTING"
    RESPONDING = "RESPONDING"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"
    RECOVERY = "RECOVERY"
    ENDED = "ENDED"


class Language(StrEnum):
    """docs/phase-5 §21."""

    EN = "EN"
    TA = "TA"
    TA_EN = "TA_EN"
    UNKNOWN = "UNKNOWN"


class InterruptionType(StrEnum):
    """docs/phase-5 §14."""

    STOP_SPEAKING = "STOP_SPEAKING"
    CANCEL_TASK = "CANCEL_TASK"
    PAUSE_TASK = "PAUSE_TASK"
    END_SESSION = "END_SESSION"


class ConnectivityState(StrEnum):
    """docs/phase-5 §56."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    LIMITED = "LIMITED"
    UNKNOWN = "UNKNOWN"


class WakeWordMode(StrEnum):
    """docs/phase-5 §65. Default is WAKE_WORD_ONLY."""

    WAKE_WORD_ONLY = "WAKE_WORD_ONLY"
    PUSH_TO_TALK = "PUSH_TO_TALK"
    VOICE_ACTIVATION = "VOICE_ACTIVATION"
    HYBRID = "HYBRID"


class ActivationSource(StrEnum):
    """How a `VoiceSession` started — one of `VoiceSession`'s brief §12
    fields."""

    WAKE_WORD = "WAKE_WORD"
    PUSH_TO_TALK = "PUSH_TO_TALK"
    HOTKEY = "HOTKEY"
    API = "API"


class ConfirmationDecision(StrEnum):
    """docs/phase-5 §46-48 — a spoken reply to a confirmation prompt
    resolves to exactly one of these; UNCLEAR must never be treated as
    AFFIRM (brief §48: 'never treat unclear audio as authorization')."""

    AFFIRM = "AFFIRM"
    DENY = "DENY"
    UNCLEAR = "UNCLEAR"


class STTMode(StrEnum):
    """docs/phase-5 §17-19."""

    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    AUTO = "AUTO"


class VisemeShape(StrEnum):
    """docs/phase-6/LIP-SYNC.md — a small, closed set of mouth-shape
    buckets `voice.core.visemes.text_to_visemes` classifies characters
    into. A generic, simplified grouping by mouth shape, not any single
    vendor's or product's proprietary viseme set."""

    REST = "REST"
    AI = "AI"
    E = "E"
    FV = "FV"
    L = "L"
    MBP = "MBP"
    OH = "OH"
    U = "U"
    WQ = "WQ"
    ETC = "ETC"
