"""GET /health (liveness) and GET /ready (readiness) — Part 5: distinct
concepts, both real. `/health` answers "is this process alive enough to
respond to HTTP at all" — reachable as soon as the ASGI server starts
accepting connections, before the lifespan's startup work even begins.
`/ready` answers "has that startup work — migrations, tool registration —
actually finished" (docs/phase-10/PRODUCTION-AUDIT.md: previously there
was no distinct readiness signal at all, only the full `/system` report).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.readiness import is_ready

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class ReadyResponse(BaseModel):
    ready: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(UTC))


@router.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    ready_now = is_ready()
    # A caller polling for readiness should be able to check the status
    # code alone — 503 while starting up, 200 once real (never a bare
    # 200 that then has to be parsed to discover startup isn't done).
    response.status_code = status.HTTP_200_OK if ready_now else status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(ready=ready_now)
