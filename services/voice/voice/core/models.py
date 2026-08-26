"""Platform-independent voice data models. docs/phase-5/VOICE-ARCHITECTURE.md.

None of these carry raw audio bytes — brief §50-51: audio is processed
and discarded, never persisted by default. See `VOICE-PRIVACY.md`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from veyra_contracts import AmbiguityCandidate, ErrorInfo, TaskState

from voice.core.enums import (
    ActivationSource,
    ConfirmationDecision,
    InterruptionType,
    Language,
    VoiceState,
)


def _new_id() -> str:
    return uuid.uuid4().hex


class AudioDeviceInfo(BaseModel):
    """docs/phase-5 §5-6 — `AudioDeviceManager`/`AudioOutputManager`
    enumeration result. Never a raw OS handle — an opaque, backend-scoped
    id, same discipline as `computer_control.core.models.WindowInfo.handle`."""

    id: str
    name: str
    is_input: bool
    is_default: bool = False
    is_connected: bool = True


class WakeWordActivation(BaseModel):
    """docs/phase-5 §8/§10 — `activation confidence`; below-threshold
    activations are never surfaced as a real wake (`WakeWordDetector`
    implementations filter these before returning)."""

    detected: bool
    phrase: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class TranscriptChunk(BaseModel):
    """docs/phase-5 §15 — one partial or final STT result."""

    text: str
    is_final: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    language: Language = Language.UNKNOWN
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LanguageDetectionResult(BaseModel):
    """docs/phase-5 §21."""

    language: Language
    confidence: float = Field(ge=0.0, le=1.0)
    mixed_language: bool = False


class NormalizedCommand(BaseModel):
    """docs/phase-5 §23 — `SpeechNormalizer`'s output. `corrections`
    records what changed, for observability; normalization never invents
    entities (brief's own constraint), only cleans up what was said."""

    raw_text: str
    normalized_text: str
    corrections: list[str] = Field(default_factory=list)


class InterruptionResult(BaseModel):
    """docs/phase-5 §14 — `matched=False` means the utterance is ordinary
    speech, not an interruption command at all."""

    matched: bool
    interruption_type: InterruptionType | None = None
    matched_phrase: str | None = None


class ConfirmationResult(BaseModel):
    """docs/phase-5 §46-48. `UNCLEAR` (including low confidence) must
    never be treated as `AFFIRM` by any caller."""

    decision: ConfirmationDecision
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class VoiceResponse(BaseModel):
    """docs/phase-5/RESPONSE — `ResponseGenerator`'s output. `should_speak`
    lets a caller distinguish 'nothing to say yet' (e.g. still executing)
    from an actual empty response."""

    text: str
    language: Language = Language.EN
    should_speak: bool = True


class VoiceSession(BaseModel):
    """docs/phase-5 §12. The brief lists both `conversation_state` and
    `session_status` with the same value set (IDLE/LISTENING/...) —
    unified here into the single `status` field rather than two fields
    that could silently disagree; see
    docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §6."""

    id: str = Field(default_factory=_new_id)
    user_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    language: Language = Language.UNKNOWN
    status: VoiceState = VoiceState.IDLE
    active_task_id: str | None = None
    activation_source: ActivationSource = ActivationSource.API
    audio_device: str | None = None
    conversation_id: str | None = None
    # docs/phase-5 §29-30 — short-term follow-up/pronoun context: the
    # most recent ambiguity candidates a task returned, so "the second
    # one"/"open it" can resolve without repeating the full command. Never
    # more than one turn's worth — see voice.core.followup.
    last_candidates: list[AmbiguityCandidate] = Field(default_factory=list)
    last_task_goal: str | None = None


class TaskOutcome(BaseModel):
    """docs/phase-5 §74-79 — what `ResponseGenerator` speaks from. Carries
    the *real* terminal/waiting `TaskState` a Phase 4 task reached, never a
    voice-layer guess — brief §77: "If Phase 4 reports FAILED, VEYRA must
    not say Done." Deliberately narrower than the full local-api `Task`
    row: this package has no DB dependency
    (docs/phase-5/PHASE-5-IMPLEMENTATION-PLAN.md §4), so `app/services/voice`
    maps a real `Task` into this shape before calling `generate_response`.
    """

    state: TaskState
    goal: str | None = None
    result_summary: str | None = None
    error: ErrorInfo | None = None
    candidates: list[AmbiguityCandidate] = Field(default_factory=list)
    # The real text Phase 4 already generated for a WAITING_USER/
    # WAITING_PERMISSION pause (`Task.result["clarifying_question"]` or
    # `["confirmation_prompt"]`) — spoken verbatim, never re-derived or
    # paraphrased, so VEYRA asks exactly what Phase 4 actually needs
    # answered.
    clarifying_question: str | None = None
    confirmation_prompt: str | None = None
