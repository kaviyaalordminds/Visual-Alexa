"""VoiceConversationManager — binds the voice pipeline to the real Task
Engine. docs/phase-5/CONVERSATION.md, brief §27-31/§44-49.

The one architectural rule this class exists to uphold (brief §27): a
voice turn's *normalized transcript* becomes an ordinary `Task.description`
run through the real, unmodified `AgentOrchestrator` — this class never
calls `IntentInterpreter` itself, only decides what text to submit (after
normalization + follow-up rewriting) and how to speak whatever terminal/
waiting `TaskState` is reached. It also never grants itself anything a
typed command couldn't get: confirmation still goes through the exact same
`apply_confirmation_decision` the HTTP `/tasks/{id}/confirm` route uses,
and `ALLOW_ONCE` only ever — no voice-only `ALWAYS_ALLOW` shortcut (brief
§131: "the voice interface is NOT a security bypass").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import (
    AmbiguityCandidate,
    ErrorCategory,
    ErrorInfo,
    PermissionDecision,
    TaskBudget,
    TaskState,
)
from voice.core.confirmation import parse_confirmation
from voice.core.enums import ActivationSource, ConfirmationDecision, InterruptionType, VoiceState
from voice.core.followup import resolve_followup
from voice.core.interruption import classify_interruption
from voice.core.language import detect_language
from voice.core.models import InterruptionResult, Language, TaskOutcome, VoiceResponse
from voice.core.models import VoiceSession as VoiceSessionModel
from voice.core.normalizer import normalize_command
from voice.core.privacy import redact_secrets
from voice.core.response import ask_yes_no_text, cancelled_text, generate_response, goodbye_text
from voice.core.state_machine import VoiceStateMachine

from app.api.deps import get_or_create_local_user
from app.models.conversation import Conversation as ConversationRow
from app.models.conversation import Message as MessageRow
from app.models.task import Task as TaskRow
from app.models.voice import VoiceSessionRow
from app.services.agent.confirmation_actions import apply_confirmation_decision
from app.services.agent.orchestrator import request_cancellation
from app.services.agent.register import get_orchestrator

# docs/phase-5 §11 — a voice turn's default TaskBudget: matches the common
# default already used elsewhere for a single bounded turn (see
# tests/unit/test_agent_recovery.py) rather than inventing a new one.
_VOICE_TASK_BUDGET = TaskBudget(max_steps=10, timeout_seconds=60, max_recovery_attempts=2)


def _effective_language(session: VoiceSessionModel) -> Language:
    return session.language if session.language != Language.UNKNOWN else Language.EN


class UnknownVoiceSessionError(KeyError):
    """Raised when a caller references a voice session id this manager
    has no in-memory record of (never started, or already ended)."""


@dataclass
class VoiceTurnResult:
    session: VoiceSessionModel
    response: VoiceResponse
    # True when this turn interrupted VEYRA's own ongoing speech and the
    # caller (the real AudioOutput) must stop playback immediately.
    stop_speaking: bool = False
    ended: bool = False


def _now() -> datetime:
    return datetime.now(UTC)


class VoiceConversationManager:
    """One process-wide instance (mirrors `AgentOrchestrator`'s own
    singleton, `app/services/agent/register.py`) — in-memory registry of
    active `VoiceSession`s. This process is the only one that ever runs a
    voice turn (CLAUDE.md: the Local API is the only process with database
    access), so an in-memory dict is sufficient, exactly like
    `orchestrator.py`'s own `_cancellation_events` registry."""

    def __init__(self) -> None:
        self._sessions: dict[str, VoiceSessionModel] = {}

    def get(self, session_id: str) -> VoiceSessionModel | None:
        return self._sessions.get(session_id)

    async def start_session(
        self,
        db: AsyncSession,
        *,
        user_id: str | None = None,
        activation_source: ActivationSource = ActivationSource.API,
        audio_device: str | None = None,
        conversation_id: str | None = None,
    ) -> VoiceSessionModel:
        if conversation_id is None:
            # docs/phase-5 §8 — transcripts reuse the existing Conversation/
            # Message tables rather than a new one; every voice session
            # gets a real conversation so its turns are inspectable via
            # the existing GET /conversations/{id}/messages (no new,
            # voice-only transcript surface to keep consistent).
            user = await get_or_create_local_user(db)
            conversation = ConversationRow(user_id=user.id, title="Voice session")
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
            conversation_id = conversation.id

        session = VoiceSessionModel(
            user_id=user_id,
            activation_source=activation_source,
            audio_device=audio_device,
            conversation_id=conversation_id,
        )
        sm = VoiceStateMachine(session)
        # Wake-word/hotkey activation already implies the user is about to
        # speak; API-initiated sessions go straight to LISTENING too —
        # Phase 5 ships no real wake-word detector (docs/phase-5/
        # PHASE-5-IMPLEMENTATION-PLAN.md §3), so WAKE_DETECTED would never
        # otherwise be exercised as a real, reachable state here.
        sm.transition(VoiceState.LISTENING)
        self._sessions[session.id] = session
        await self._persist(db, session)
        return session

    async def end_session(self, db: AsyncSession, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        if session.active_task_id is not None:
            request_cancellation(session.active_task_id)
        sm = VoiceStateMachine(session)
        if sm.can_transition(VoiceState.ENDED):
            sm.transition(VoiceState.ENDED)
        await self._persist(db, session, ended=True)

    async def finish_response(self, db: AsyncSession, session_id: str) -> VoiceSessionModel:
        """Call once real TTS playback of the last response actually
        finishes (or immediately, for a text-only caller) — transitions
        RESPONDING -> IDLE. Separate from `submit_utterance` because
        real playback is asynchronous with respect to when the text was
        generated; barge-in (`submit_utterance` called again while still
        RESPONDING) is what happens if this is never reached."""
        session = self._require_session(session_id)
        sm = VoiceStateMachine(session)
        if sm.can_transition(VoiceState.IDLE):
            sm.transition(VoiceState.IDLE)
        await self._persist(db, session)
        return session

    async def submit_utterance(
        self,
        db: AsyncSession,
        session_id: str,
        raw_text: str,
        *,
        stt_confidence: float = 1.0,
    ) -> VoiceTurnResult:
        session = self._require_session(session_id)
        sm = VoiceStateMachine(session)
        session.last_activity = _now()

        if session.status == VoiceState.RESPONDING:
            interruption = classify_interruption(raw_text)
            if interruption.matched:
                result = await self._handle_interruption(db, session, sm, interruption)
                if result is not None:
                    await self._log_turn(db, session, raw_text, result.response.text)
                    return result
            else:
                # Any other speech while VEYRA is talking is still a
                # barge-in (brief §13) — stop speaking, then handle the
                # utterance as an ordinary new command below.
                sm.transition(VoiceState.INTERRUPTED)
                sm.transition(VoiceState.LISTENING)

        if session.status in (VoiceState.IDLE, VoiceState.WAKE_DETECTED):
            sm.transition(VoiceState.LISTENING)

        sm.transition(VoiceState.TRANSCRIBING)

        detection = detect_language(raw_text)
        if detection.language != Language.UNKNOWN:
            session.language = detection.language
        normalized = normalize_command(raw_text)

        sm.transition(VoiceState.UNDERSTANDING)

        pending_task = await self._get_pending_task(db, session)

        if pending_task is not None and pending_task.state == TaskState.WAITING_PERMISSION:
            response = await self._handle_confirmation(
                db, session, sm, pending_task, normalized.normalized_text, stt_confidence
            )
            await self._persist(db, session)
            await self._log_turn(db, session, raw_text, response.text)
            return VoiceTurnResult(session=session, response=response)

        effective_text = resolve_followup(normalized.normalized_text, session) or (
            normalized.normalized_text
        )

        user = await get_or_create_local_user(db)
        task = TaskRow(
            user_id=session.user_id or user.id,
            conversation_id=session.conversation_id,
            description=effective_text,
            state=TaskState.RECEIVED,
            max_steps=_VOICE_TASK_BUDGET.max_steps,
            timeout_seconds=_VOICE_TASK_BUDGET.timeout_seconds,
            max_recovery_attempts=_VOICE_TASK_BUDGET.max_recovery_attempts,
            max_replans=_VOICE_TASK_BUDGET.max_replans,
            correlation_id=str(uuid4()),
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        session.active_task_id = task.id
        session.last_task_goal = effective_text

        sm.transition(VoiceState.EXECUTING)
        await get_orchestrator().run(db, task)

        response = self._respond_to_task(session, task)
        sm.transition(VoiceState.RESPONDING)
        await self._persist(db, session)
        await self._log_turn(db, session, raw_text, response.text)
        return VoiceTurnResult(session=session, response=response)

    async def _handle_interruption(
        self,
        db: AsyncSession,
        session: VoiceSessionModel,
        sm: VoiceStateMachine,
        interruption: InterruptionResult,
    ) -> VoiceTurnResult | None:
        sm.transition(VoiceState.INTERRUPTED)
        kind = interruption.interruption_type

        language = _effective_language(session)

        if kind == InterruptionType.STOP_SPEAKING:
            sm.transition(VoiceState.LISTENING)
            await self._persist(db, session)
            return VoiceTurnResult(
                session=session,
                response=VoiceResponse(text="", language=language, should_speak=False),
                stop_speaking=True,
            )

        if kind == InterruptionType.CANCEL_TASK:
            if session.active_task_id is not None:
                request_cancellation(session.active_task_id)
            session.active_task_id = None
            session.last_candidates = []
            sm.transition(VoiceState.LISTENING)
            await self._persist(db, session)
            return VoiceTurnResult(
                session=session,
                response=VoiceResponse(
                    text=cancelled_text(language), language=language, should_speak=True
                ),
                stop_speaking=True,
            )

        if kind == InterruptionType.PAUSE_TASK:
            # docs/phase-5/BARGE-IN.md — known limitation: Phase 4's
            # AgentOrchestrator has no real pause/resume mechanism (only
            # cancellation and confirmation-resume), so PAUSE_TASK only
            # ever pauses VEYRA's *speech*, never the underlying task
            # execution. This is intentionally not represented as a
            # stronger guarantee than it delivers.
            sm.transition(VoiceState.LISTENING)
            await self._persist(db, session)
            return VoiceTurnResult(
                session=session,
                response=VoiceResponse(text="", language=language, should_speak=False),
                stop_speaking=True,
            )

        if kind == InterruptionType.END_SESSION:
            if session.active_task_id is not None:
                request_cancellation(session.active_task_id)
            sm.transition(VoiceState.ENDED)
            await self._persist(db, session, ended=True)
            self._sessions.pop(session.id, None)
            return VoiceTurnResult(
                session=session,
                response=VoiceResponse(
                    text=goodbye_text(language), language=language, should_speak=True
                ),
                stop_speaking=True,
                ended=True,
            )

        return None  # pragma: no cover - unreachable, every InterruptionType is handled above

    async def _handle_confirmation(
        self,
        db: AsyncSession,
        session: VoiceSessionModel,
        sm: VoiceStateMachine,
        task: TaskRow,
        normalized_text: str,
        stt_confidence: float,
    ) -> VoiceResponse:
        confirmation = parse_confirmation(normalized_text, confidence=stt_confidence)

        if confirmation.decision == ConfirmationDecision.UNCLEAR:
            # brief §48 — never treat unclear audio as authorization.
            # Nothing executed; go straight back to speaking, no
            # EXECUTING step attempted.
            sm.transition(VoiceState.RESPONDING)
            language = _effective_language(session)
            return VoiceResponse(
                text=ask_yes_no_text(language), language=language, should_speak=True
            )

        decision = (
            PermissionDecision.ALLOW_ONCE
            if confirmation.decision == ConfirmationDecision.AFFIRM
            else PermissionDecision.DENY
        )
        resumed = await apply_confirmation_decision(db, task, decision)
        if resumed:
            sm.transition(VoiceState.EXECUTING)
            await get_orchestrator().resume_after_confirmation(db, task)
        response = self._respond_to_task(session, task)
        sm.transition(VoiceState.RESPONDING)
        return response

    def _respond_to_task(self, session: VoiceSessionModel, task: TaskRow) -> VoiceResponse:
        if task.state in (TaskState.WAITING_USER, TaskState.WAITING_PERMISSION):
            session.active_task_id = task.id
        else:
            session.active_task_id = None
            session.last_candidates = []

        candidates: list[AmbiguityCandidate] = []
        clarifying_question: str | None = None
        confirmation_prompt: str | None = None
        result = task.result or {}
        if task.state == TaskState.WAITING_USER:
            clarifying_question = result.get("clarifying_question")
            candidates = [
                AmbiguityCandidate.model_validate(c) for c in result.get("candidates", [])
            ]
            session.last_candidates = candidates
        elif task.state == TaskState.WAITING_PERMISSION:
            confirmation_prompt = result.get("confirmation_prompt")

        error: ErrorInfo | None = None
        if task.state == TaskState.FAILED:
            error = ErrorInfo.build(
                code=task.failure_category or ErrorCategory.UNKNOWN_ERROR,
                message=task.failure_reason or "Something went wrong.",
                correlation_id=task.correlation_id,
            )

        outcome = TaskOutcome(
            state=task.state,
            goal=task.description,
            error=error,
            candidates=candidates,
            clarifying_question=clarifying_question,
            confirmation_prompt=confirmation_prompt,
        )
        return generate_response(outcome, language=_effective_language(session))

    async def _get_pending_task(
        self, db: AsyncSession, session: VoiceSessionModel
    ) -> TaskRow | None:
        if session.active_task_id is None:
            return None
        result = await db.execute(select(TaskRow).where(TaskRow.id == session.active_task_id))
        return result.scalars().first()

    def _require_session(self, session_id: str) -> VoiceSessionModel:
        session = self._sessions.get(session_id)
        if session is None:
            raise UnknownVoiceSessionError(session_id)
        return session

    async def _log_turn(
        self, db: AsyncSession, session: VoiceSessionModel, raw_text: str, response_text: str
    ) -> None:
        """docs/phase-5 §50-57 — transcripts reuse the existing Message
        table (GET /conversations/{id}/messages is the real "get
        transcript" surface), with secrets redacted before anything is
        written, never after."""
        if session.conversation_id is None:
            return
        db.add(
            MessageRow(
                conversation_id=session.conversation_id,
                role="user",
                content=redact_secrets(raw_text),
            )
        )
        if response_text:
            db.add(
                MessageRow(
                    conversation_id=session.conversation_id,
                    role="assistant",
                    content=redact_secrets(response_text),
                )
            )
        await db.commit()

    async def _persist(
        self, db: AsyncSession, session: VoiceSessionModel, *, ended: bool = False
    ) -> None:
        result = await db.execute(select(VoiceSessionRow).where(VoiceSessionRow.id == session.id))
        row = result.scalars().first()
        if row is None:
            row = VoiceSessionRow(id=session.id)
            db.add(row)
        row.user_id = session.user_id
        row.conversation_id = session.conversation_id
        row.started_at = session.started_at
        row.last_activity_at = session.last_activity
        row.language = session.language
        row.status = session.status
        row.active_task_id = session.active_task_id
        row.activation_source = session.activation_source
        row.audio_device = session.audio_device
        if ended:
            row.ended_at = _now()
        await db.commit()
