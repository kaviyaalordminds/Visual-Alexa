"""GET /browser/sessions, GET /browser/downloads, POST /browser/extension/
command. docs/phase-8/BROWSER-SESSION.md, docs/phase-8/EXTENSION-BRIDGE.md.

Every browser *action* still goes through the exact same
ToolRegistry -> PolicyEngine -> execute_tool_call chain every other tool
uses (`POST /tools/{tool_id}/invoke`) — these routes are read-only
diagnostics plus the one authenticated extension-bridge endpoint, never a
second execution path.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from veyra_contracts import BrowserSessionInfo, ExtensionCommandRequest

from app.services.browser.extension_bridge import (
    ExtensionAuthError,
    UnknownExtensionCommandError,
    extension_bridge_service,
)
from app.services.browser.manager import browser_manager
from app.services.browser.observation import observation_service

router = APIRouter(prefix="/browser", tags=["browser"])


@router.get("/sessions", response_model=list[BrowserSessionInfo])
async def list_sessions() -> list[BrowserSessionInfo]:
    return [session.to_info() for session in browser_manager.registry.list()]


@router.get("/downloads")
async def list_downloads() -> dict:
    return {
        "downloads": [
            {
                "download_id": r.download_id,
                "session_id": r.session_id,
                "filename": r.filename,
                "status": r.status,
                "destination_path": r.destination_path,
                "potentially_dangerous": r.is_potentially_dangerous,
                "started_at": r.started_at.isoformat(),
            }
            for r in browser_manager.downloads.list()
        ]
    }


@router.post("/extension/command")
async def extension_command(
    body: ExtensionCommandRequest,
    x_veyra_extension_token: str = Header(default=""),
    origin: str = Header(default=""),
) -> dict:
    try:
        return await extension_bridge_service.handle_command(
            body,
            token=x_veyra_extension_token,
            origin=origin,
            manager=browser_manager,
            observation=observation_service,
        )
    except ExtensionAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except UnknownExtensionCommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
