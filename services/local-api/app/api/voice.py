"""POST/GET /voice — session lifecycle over HTTP. docs/phase-5/
PHASE-5-IMPLEMENTATION-PLAN.md §9, brief §107-109.

Deliberately thin: every real decision (normalization, language detection,
follow-up resolution, confirmation handling, task creation/execution,
response generation) lives in `VoiceConversationManager` — this router
only turns HTTP requests into calls on it, exactly like `app/api/tasks.py`
does for `AgentOrchestrator`. No avatar/lip-sync/animation endpoints —
those are explicitly out of Phase 5 scope (brief §132).

`GET /conversations/{id}/messages` (already existing, Phase 1) is the
transcript endpoint — a voice session's `conversation_id` points there, so
no separate "get transcript" route is added here (CLAUDE.md: never
duplicate services).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from voice.core.enums import ActivationSource, Language, VoiceState

from app.db.session import get_session
from app.services.voice.manager import UnknownVoiceSessionError
from app.services.voice.register import get_voice_manager

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceSessionOut(BaseModel):
    id: str
    conversation_id: str | None
    started_at: datetime
    last_activity: datetime
    language: Language
    status: VoiceState
    active_task_id: str | None
    activation_source: ActivationSource
    audio_device: str | None


class StartSessionRequest(BaseModel):
    activation_source: ActivationSource = ActivationSource.API
    audio_device: str | None = None
    conversation_id: str | None = None


class SubmitUtteranceRequest(BaseModel):
    text: str
    stt_confidence: float = 1.0


class VoiceResponseOut(BaseModel):
    text: str
    language: Language
    should_speak: bool


class VoiceTurnOut(BaseModel):
    session: VoiceSessionOut
    response: VoiceResponseOut
    stop_speaking: bool
    ended: bool


def _session_out(session) -> VoiceSessionOut:
    return VoiceSessionOut(
        id=session.id,
        conversation_id=session.conversation_id,
        started_at=session.started_at,
        last_activity=session.last_activity,
        language=session.language,
        status=session.status,
        active_task_id=session.active_task_id,
        activation_source=session.activation_source,
        audio_device=session.audio_device,
    )


@router.post("/sessions", response_model=VoiceSessionOut, status_code=201)
async def start_session(
    body: StartSessionRequest, db: AsyncSession = Depends(get_session)
) -> VoiceSessionOut:
    session = await get_voice_manager().start_session(
        db,
        activation_source=body.activation_source,
        audio_device=body.audio_device,
        conversation_id=body.conversation_id,
    )
    return _session_out(session)


@router.get("/sessions/{session_id}", response_model=VoiceSessionOut)
async def get_voice_session(session_id: str) -> VoiceSessionOut:
    session = get_voice_manager().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown voice session '{session_id}'.")
    return _session_out(session)


@router.post("/sessions/{session_id}/utterances", response_model=VoiceTurnOut)
async def submit_utterance(
    session_id: str, body: SubmitUtteranceRequest, db: AsyncSession = Depends(get_session)
) -> VoiceTurnOut:
    try:
        result = await get_voice_manager().submit_utterance(
            db, session_id, body.text, stt_confidence=body.stt_confidence
        )
    except UnknownVoiceSessionError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown voice session '{exc}'.") from exc
    return VoiceTurnOut(
        session=_session_out(result.session),
        response=VoiceResponseOut(
            text=result.response.text,
            language=result.response.language,
            should_speak=result.response.should_speak,
        ),
        stop_speaking=result.stop_speaking,
        ended=result.ended,
    )


@router.post("/sessions/{session_id}/finish_response", response_model=VoiceSessionOut)
async def finish_response(
    session_id: str, db: AsyncSession = Depends(get_session)
) -> VoiceSessionOut:
    try:
        session = await get_voice_manager().finish_response(db, session_id)
    except UnknownVoiceSessionError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown voice session '{exc}'.") from exc
    return _session_out(session)


@router.post("/sessions/{session_id}/end", status_code=204)
async def end_session(session_id: str, db: AsyncSession = Depends(get_session)) -> None:
    await get_voice_manager().end_session(db, session_id)
