"""GET /tools, POST /tools/{tool_id}/invoke.
docs/architecture/04-TOOL-ARCHITECTURE.md, docs/security/01-SECURITY-ARCHITECTURE.md.

/invoke exercises the full Policy Engine -> Registry -> Executor -> Audit ->
Event chain end-to-end. It is not a general "run any tool" backdoor for a
future planner — a live planner would call `execute_tool_call` directly
in-process; this HTTP endpoint exists so Phase 1's registry/policy/executor
wiring is demonstrable and testable through the same API surface a future
UI would use.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from veyra_contracts import ToolCallRequest, ToolCategory, ToolDefinition, ToolResult

from app.api.deps import get_or_create_local_user
from app.db.session import get_session
from app.services.tool_execution import UnknownToolError, execute_tool_call
from app.services.tool_registry import tool_registry

router = APIRouter(prefix="/tools", tags=["tools"])


class InvokeRequest(BaseModel):
    target: str | None = None
    arguments: dict[str, Any] = {}


@router.get("", response_model=list[ToolDefinition])
async def list_tools(category: ToolCategory | None = None) -> list[ToolDefinition]:
    return tool_registry.list(category=category)


@router.get("/{tool_id}", response_model=ToolDefinition)
async def get_tool(tool_id: str) -> ToolDefinition:
    definition = tool_registry.get(tool_id)
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{tool_id}'.")
    return definition


@router.post("/{tool_id}/invoke", response_model=ToolResult)
async def invoke_tool(
    tool_id: str, body: InvokeRequest, session: AsyncSession = Depends(get_session)
) -> ToolResult:
    user = await get_or_create_local_user(session)
    call = ToolCallRequest(
        tool_id=tool_id,
        target=body.target,
        arguments=body.arguments,
        correlation_id=str(uuid4()),
    )
    try:
        outcome = await execute_tool_call(session, tool_registry, call=call, user_id=user.id)
    except UnknownToolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return outcome.result
