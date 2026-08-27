"""ExtensionBridgeService — the secure local bridge brief §71-75 asks for:

    VEYRA Desktop <-> Authenticated Local Bridge <-> VEYRA Browser Extension <-> Browser Tab

No packaged browser extension ships in this phase (brief §171 — build the
architecture, not every integration) — this module is the "Authenticated
Local Bridge" half, real and testable on its own: token authentication,
origin validation, and a closed command set. docs/phase-8/EXTENSION-BRIDGE.md.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from veyra_contracts import ErrorCategory, ExtensionCommandRequest

from app.services.browser.manager import BrowserManager
from app.services.browser.observation import ObservationService

# brief §74 — the closed set. No `execute_arbitrary_command` exists here
# or anywhere else in this module; an unlisted command name is rejected
# before it can reach anything.
ALLOWED_COMMANDS = frozenset(
    {"get_page_state", "get_active_tab", "highlight_element", "request_action"}
)


class ExtensionAuthError(Exception):
    code = ErrorCategory.EXTENSION_AUTH_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownExtensionCommandError(Exception):
    code = ErrorCategory.VALIDATION_ERROR

    def __init__(self, command: str) -> None:
        super().__init__(f"'{command}' is not an approved extension command.")
        self.command = command


@dataclass
class QueuedAction:
    """brief §75 — a webpage must never be able to directly invoke VEYRA.
    Even an *authenticated* extension's `request_action` command is only
    ever queued for a human/agent to review, never auto-executed — this
    bridge has no path from a request straight into `execute_tool_call`."""

    tab_id: str | None
    description: str


class ExtensionBridgeService:
    def __init__(self, *, allowed_origins: frozenset[str] = frozenset()) -> None:
        # brief §72 — 'do not accept arbitrary localhost requests.' A
        # fresh, random, in-memory-only token per process start; nothing
        # persists it, so every restart requires the desktop app to
        # re-display it and the extension to be re-paired. Never a
        # hard-coded/default value.
        self.token = secrets.token_urlsafe(32)
        self._allowed_origins = allowed_origins
        self.queued_actions: list[QueuedAction] = []

    def authenticate(self, *, token: str, origin: str) -> None:
        if not hmac.compare_digest(token, self.token):
            raise ExtensionAuthError("Invalid or missing bridge token.")
        if origin not in self._allowed_origins:
            raise ExtensionAuthError(
                f"Origin '{origin}' is not an authorized VEYRA extension origin."
            )

    async def handle_command(
        self,
        request: ExtensionCommandRequest,
        *,
        token: str,
        origin: str,
        manager: BrowserManager,
        observation: ObservationService,
    ) -> dict:
        self.authenticate(token=token, origin=origin)
        if request.command not in ALLOWED_COMMANDS:
            raise UnknownExtensionCommandError(request.command)

        if request.command == "get_active_tab":
            tab = manager.current_tab(None)
            return {"tab_id": tab.tab_id, "url": tab.url, "title": tab.title}

        if request.command == "get_page_state":
            session, tab = manager.resolve_tab_target(request.tab_id)
            page = await observation.observe(
                session.adapter, tab.tab_ref, tab_id=tab.tab_id, manager=manager
            )
            return page.model_dump()

        if request.command == "highlight_element":
            element_id = request.payload.get("element_id")
            if not element_id:
                raise ValueError("'element_id' is required for highlight_element.")
            session, tab = manager.resolve_tab_target(request.tab_id)
            await session.adapter.scroll_into_view(tab.tab_ref, element_id)
            return {"highlighted": element_id}

        # request_action
        description = str(request.payload.get("description", ""))
        self.queued_actions.append(QueuedAction(tab_id=request.tab_id, description=description))
        return {"queued": True}


def _default_allowed_origins() -> frozenset[str]:
    from app.core.config import get_settings

    return frozenset(get_settings().browser_extension_origins)


# Process-wide singleton, like `browser_manager`/`observation_service`.
extension_bridge_service = ExtensionBridgeService(allowed_origins=_default_allowed_origins())
