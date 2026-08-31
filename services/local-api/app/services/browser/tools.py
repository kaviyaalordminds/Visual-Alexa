"""Every `browser.*` (and `web.research`) tool, registered through the
existing Phase 7 `ToolRegistry` exactly like every other capability in
this codebase (brief §7/§76 — "Implement through Phase 7 ToolRegistry").
docs/phase-8/BROWSER-TOOLS.md.

Every state-changing tool (click/type/select/upload/fill_form) calls
`BrowserActionGuard.check_before_action` first — the one place CAPTCHA/
OTP/payment stop conditions are enforced (brief §22-24/§40). Every tool
returns extracted page text as inert `ToolResult.output` data, never
feeds it back into anything that treats it as an instruction (brief
§36-38/§97) — the structural half of this phase's prompt-injection
defense.

Two `target` conventions, matching `BrowserManager`'s own split:
session-scoped tools (`browser.close`/`focus`/`new_tab`/`list_tabs`/
`current_tab`/`find_tab`, `download.list`) take a session_id (or None for
the active session); every other tab-scoped tool takes a tab_id (or None
for the active session's active tab), resolved via
`BrowserManager.resolve_tab_target`.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote_plus

from veyra_contracts import (
    AgentState,
    ConfirmationPolicy,
    ErrorCategory,
    ErrorInfo,
    EventType,
    EvidenceTier,
    RiskLevel,
    ToolCallRequest,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolResultStatus,
)

from app.core.event_bus import event_bus
from app.services.audit import SENSITIVE_FIELD_HINTS
from app.services.browser.adapter import AdapterError, DownloadEvent
from app.services.browser.elements import ElementFusionEngine
from app.services.browser.manager import (
    BrowserManager,
    BrowserManagerError,
    BrowserSession,
    BrowserTab,
    UnknownSessionError,
    UnknownTabError,
)
from app.services.browser.observation import ObservationService
from app.services.browser.research import ResearchBudgetExceeded, WebResearchAgent
from app.services.browser.security import (
    BrowserActionGuard,
    BrowserStopCondition,
    InstructionBoundary,
    SecretRedactor,
    URLValidator,
    WebContentSanitizer,
)
from app.services.browser.workflow import BrowserWorkflowEngine
from app.services.tool_registry import ToolExecutor

# brief §20/§463 — never automatically fill these into any form field.
# Reuses `audit.py`'s `SENSITIVE_FIELD_HINTS` (which also drives §129's
# "never log the typed value" redaction) rather than a second, separately
# maintained list the two checks could drift apart from.
_SENSITIVE_FIELD_LABELS = SENSITIVE_FIELD_HINTS

_SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "spotify": "https://open.spotify.com/search/{q}",
}


@dataclass
class BrowserToolContext:
    manager: BrowserManager
    observation: ObservationService
    fusion: ElementFusionEngine
    url_validator: URLValidator
    sanitizer: WebContentSanitizer
    redactor: SecretRedactor
    boundary: InstructionBoundary
    guard: BrowserActionGuard
    research: WebResearchAgent
    workflow: BrowserWorkflowEngine
    ocr_engine: object | None = None


class _ToolLogicError(Exception):
    def __init__(
        self, code: ErrorCategory, message: str, *, user_action_required: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.user_action_required = user_action_required


_MANAGER_ERROR_MAP: dict[type[Exception], ErrorCategory] = {
    UnknownSessionError: ErrorCategory.VALIDATION_ERROR,
    UnknownTabError: ErrorCategory.VALIDATION_ERROR,
    BrowserManagerError: ErrorCategory.RESOURCE_BUSY,
    AdapterError: ErrorCategory.TOOL_FAILURE,
}


def _map_exception(exc: Exception) -> tuple[ErrorCategory, str]:
    for exc_type, code in _MANAGER_ERROR_MAP.items():
        if isinstance(exc, exc_type):
            return code, str(exc)
    return ErrorCategory.UNKNOWN_ERROR, str(exc)


def _browser_executor(
    tool_id: str, fn: Callable[[ToolCallRequest], Awaitable[dict | None]]
) -> ToolExecutor:
    class _Executor:
        async def execute(self, call: ToolCallRequest) -> ToolResult:
            started = time.monotonic()
            try:
                output = await fn(call)
                return ToolResult(
                    call_id=call.call_id,
                    status=ToolResultStatus.SUCCESS,
                    output=output or {},
                    evidence_tier_used=EvidenceTier.BROWSER_DOM,
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
            except _ToolLogicError as exc:
                return ToolResult(
                    call_id=call.call_id,
                    status=ToolResultStatus.FAILURE,
                    error=ErrorInfo.build(
                        exc.code,
                        exc.message,
                        call.correlation_id,
                        user_action_required=exc.user_action_required,
                    ),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
            except (UnknownSessionError, UnknownTabError, BrowserManagerError, AdapterError) as exc:
                code, message = _map_exception(exc)
                return ToolResult(
                    call_id=call.call_id,
                    status=ToolResultStatus.FAILURE,
                    error=ErrorInfo.build(code, message, call.correlation_id),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )

        __name__ = tool_id

    return _Executor()


def _def(
    tool_id: str,
    name: str,
    description: str,
    *,
    input_schema: dict,
    risk_level: RiskLevel,
    keywords: list[str],
    confirmation: ConfirmationPolicy = ConfirmationPolicy.NEVER,
) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=name,
        description=description,
        category=ToolCategory.BROWSER,
        input_schema=input_schema,
        output_schema={"type": "object"},
        risk_level=risk_level,
        required_permission=f"browser.{tool_id}",
        confirmation_policy=confirmation,
        keywords=keywords,
    )


async def _publish_avatar_state(call: ToolCallRequest, state: AgentState) -> None:
    """brief §139/§164 — BROWSING/SEARCHING/READING/BLOCKED, set directly
    (no TaskState equivalent) over the same shared `voice.ui_state.
    changed` channel Phase 6 established as *the* avatar-state broadcast
    — never voice-exclusive despite the wire event name (see that
    module's own docstring)."""
    await event_bus.publish_type(
        EventType.VOICE_UI_STATE_CHANGED, call.correlation_id, {"agent_state": state.value}
    )


async def _check_action_guard(
    ctx: BrowserToolContext,
    call: ToolCallRequest,
    session: BrowserSession,
    tab: BrowserTab,
    *,
    element_text: str | None,
) -> None:
    observation = await ctx.observation.observe(
        session.adapter, tab.tab_ref, tab_id=tab.tab_id, manager=ctx.manager
    )
    stop = ctx.guard.check_before_action(
        captcha_detected=observation.captcha_detected,
        otp_detected=observation.otp_detected,
        element_text=element_text,
    )
    if stop is None:
        return
    await _publish_avatar_state(call, AgentState.BLOCKED)
    # Phase 12 — a security-observability event distinct from the
    # avatar-state broadcast above: this is the one place all three
    # in-page browser stop-conditions (CAPTCHA/OTP/payment) converge, so
    # it's the natural single chokepoint to publish from rather than
    # duplicating this call at each raise below.
    await event_bus.publish_type(
        EventType.SECURITY_BLOCKED, call.correlation_id, {"reason": stop.value}
    )
    if stop == BrowserStopCondition.CAPTCHA:
        raise _ToolLogicError(
            ErrorCategory.CAPTCHA_DETECTED,
            "A CAPTCHA was detected on this page. VEYRA has stopped automation — please "
            "complete it yourself, then ask VEYRA to continue.",
            user_action_required=True,
        )
    if stop == BrowserStopCondition.OTP:
        raise _ToolLogicError(
            ErrorCategory.OTP_REQUIRED,
            "This page requires a one-time passcode. VEYRA has stopped automation — please "
            "enter it yourself.",
            user_action_required=True,
        )
    if stop == BrowserStopCondition.PAYMENT:
        raise _ToolLogicError(
            ErrorCategory.PAYMENT_CONFIRMATION_REQUIRED,
            "This looks like a payment/checkout action. VEYRA never completes a purchase "
            "autonomously — please confirm and complete this step yourself.",
            user_action_required=True,
        )


async def _resolve_element(
    ctx: BrowserToolContext,
    session: BrowserSession,
    tab: BrowserTab,
    query: str | None,
    element_id: str | None,
) -> str:
    if element_id:
        return element_id
    if not query:
        raise _ToolLogicError(
            ErrorCategory.VALIDATION_ERROR, "'query' or 'element_id' is required."
        )
    resolution = await ctx.fusion.resolve(
        session.adapter, tab.tab_ref, query, ocr_engine=ctx.ocr_engine
    )
    if resolution.ambiguous:
        raise _ToolLogicError(
            ErrorCategory.AMBIGUOUS_TARGET,
            f"Multiple elements match '{query}' with similar confidence — please be more specific.",
            user_action_required=True,
        )
    if resolution.best is None:
        raise _ToolLogicError(ErrorCategory.UI_NOT_FOUND, f"No element found matching '{query}'.")
    return resolution.best.element_id


def build_browser_tools(ctx: BrowserToolContext) -> list[tuple[ToolDefinition, ToolExecutor]]:
    m = ctx.manager

    # --- session-scoped tools: call.target is a session_id (or None) ---

    async def launch(call: ToolCallRequest) -> dict:
        session = await m.launch(headless=bool(call.arguments.get("headless", True)))
        return {"session_id": session.session_id, "tab_id": session.active_tab_id}

    async def close(call: ToolCallRequest) -> dict:
        await m.close(call.target)
        return {"closed": True}

    async def focus(call: ToolCallRequest) -> dict:
        if not call.target:
            raise _ToolLogicError(
                ErrorCategory.VALIDATION_ERROR, "A session id (target) is required."
            )
        return {"session_id": m.focus(call.target).session_id}

    async def new_tab(call: ToolCallRequest) -> dict:
        tab = await m.new_tab(call.target, url=call.arguments.get("url"))
        return {"tab_id": tab.tab_id, "url": tab.url}

    async def list_tabs(call: ToolCallRequest) -> dict:
        session = m.require_session(call.target)
        tabs = m.list_tabs(call.target)
        return {
            "tabs": [t.to_info(active=t.tab_id == session.active_tab_id).model_dump() for t in tabs]
        }

    async def current_tab(call: ToolCallRequest) -> dict:
        tab = m.current_tab(call.target)
        return {"tab_id": tab.tab_id, "url": tab.url, "title": tab.title}

    async def find_tab(call: ToolCallRequest) -> dict:
        tab = m.find_tab(call.target, call.arguments.get("query", ""))
        if tab is None:
            return {"found": False}
        return {"found": True, "tab_id": tab.tab_id, "url": tab.url, "title": tab.title}

    async def download_list(call: ToolCallRequest) -> dict:
        return {
            "downloads": [
                {
                    "download_id": r.download_id,
                    "filename": r.filename,
                    "status": r.status,
                    "destination_path": r.destination_path,
                    "potentially_dangerous": r.is_potentially_dangerous,
                    "started_at": r.started_at.isoformat(),
                }
                for r in m.downloads.list(session_id=call.target)
            ]
        }

    # --- tab-scoped tools: call.target is a tab_id (or None) ---

    async def close_tab(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        await m.close_tab(session.session_id, tab.tab_id)
        return {"closed": True}

    async def switch_tab(call: ToolCallRequest) -> dict:
        if not call.target:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "A tab id (target) is required.")
        session, tab = m.resolve_tab_target(call.target)
        m.switch_tab(session.session_id, tab.tab_id)
        return {"tab_id": tab.tab_id, "url": tab.url}

    async def navigate(call: ToolCallRequest) -> dict:
        url = call.arguments.get("url")
        if not url:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'url' is required.")
        validation = ctx.url_validator.validate(url)
        if not validation.allowed:
            await event_bus.publish_type(
                EventType.SECURITY_BLOCKED, call.correlation_id, {"reason": "UNSAFE_URL"}
            )
            raise _ToolLogicError(
                ErrorCategory.UNSAFE_URL, validation.reason, user_action_required=True
            )
        await _publish_avatar_state(call, AgentState.BROWSING)
        session, tab = m.resolve_tab_target(call.target)
        tab, result = await m.navigate(session.session_id, tab.tab_id, url)
        if not result.ok:
            raise _ToolLogicError(
                ErrorCategory.NAVIGATION_FAILED, result.error or "Navigation failed."
            )
        return {
            "tab_id": tab.tab_id,
            "final_url": result.final_url,
            "title": result.title,
            "redirect_chain": list(result.redirect_chain),
            "suspicious_redirect": ctx.url_validator.redirect_is_suspicious(url, result.final_url),
        }

    async def back(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        tab, result = await m.go_back(session.session_id, tab.tab_id)
        return {"tab_id": tab.tab_id, "url": result.final_url}

    async def forward(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        tab, result = await m.go_forward(session.session_id, tab.tab_id)
        return {"tab_id": tab.tab_id, "url": result.final_url}

    async def reload(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        tab, result = await m.reload(session.session_id, tab.tab_id)
        return {"tab_id": tab.tab_id, "url": result.final_url}

    async def stop_loading(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        await m.stop_loading(session.session_id, tab.tab_id)
        return {"stopped": True}

    async def search(call: ToolCallRequest) -> dict:
        query = call.arguments.get("query")
        if not query:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'query' is required.")
        engine = (call.arguments.get("engine") or "google").lower()
        template = _SEARCH_ENGINES.get(engine)
        if template is None:
            raise _ToolLogicError(
                ErrorCategory.VALIDATION_ERROR,
                f"Unknown search engine '{engine}'. Supported: {sorted(_SEARCH_ENGINES)}.",
            )
        await _publish_avatar_state(call, AgentState.SEARCHING)
        url = template.format(q=quote_plus(query))
        session, tab = m.resolve_tab_target(call.target)
        tab, result = await m.navigate(session.session_id, tab.tab_id, url)
        return {"tab_id": tab.tab_id, "final_url": result.final_url, "engine": engine}

    async def get_page(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        observation = await ctx.observation.observe(
            session.adapter, tab.tab_ref, tab_id=tab.tab_id, manager=m
        )
        return observation.model_dump()

    async def get_elements(call: ToolCallRequest) -> dict:
        return {"interactive_elements": (await get_page(call))["interactive_elements"]}

    async def extract_text(call: ToolCallRequest) -> dict:
        await _publish_avatar_state(call, AgentState.READING)
        session, tab = m.resolve_tab_target(call.target)
        text = await session.adapter.get_visible_text(tab.tab_ref)
        tagged = ctx.boundary.tag(ctx.sanitizer.sanitize(text))
        return tagged

    async def find(call: ToolCallRequest) -> dict:
        query = call.arguments.get("query") or call.arguments.get("text")
        if not query:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'query' is required.")
        session, tab = m.resolve_tab_target(call.target)
        resolution = await ctx.fusion.resolve(
            session.adapter, tab.tab_ref, query, ocr_engine=ctx.ocr_engine
        )
        return {
            "candidates": [c.model_dump() for c in resolution.candidates[:5]],
            "ambiguous": resolution.ambiguous,
            "best": resolution.best.model_dump() if resolution.best else None,
        }

    async def click(call: ToolCallRequest) -> dict:
        query, element_id = call.arguments.get("query"), call.arguments.get("element_id")
        x, y = call.arguments.get("x"), call.arguments.get("y")
        session, tab = m.resolve_tab_target(call.target)
        await _check_action_guard(ctx, call, session, tab, element_text=query)

        if x is not None and y is not None:
            tier = EvidenceTier.COORDINATE.value

            async def _act() -> None:
                await session.adapter.click_coordinates(tab.tab_ref, float(x), float(y))
        else:
            resolved_ref = await _resolve_element(ctx, session, tab, query, element_id)
            if resolved_ref.startswith("coord:"):
                tier = EvidenceTier.OCR.value
                _, cx, cy = resolved_ref.split(":")

                async def _act() -> None:
                    await session.adapter.click_coordinates(tab.tab_ref, float(cx), float(cy))
            else:
                tier = EvidenceTier.BROWSER_DOM.value

                async def _act() -> None:
                    await session.adapter.click(tab.tab_ref, resolved_ref)

        _, verification = await ctx.workflow.execute_and_verify(session, tab, _act)
        return {
            "tab_id": tab.tab_id,
            "evidence_tier": tier,
            "state_changed": verification.state_changed,
        }

    async def type_text(call: ToolCallRequest) -> dict:
        query, element_id = call.arguments.get("query"), call.arguments.get("element_id")
        text = call.arguments.get("text")
        if text is None:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'text' is required.")
        session, tab = m.resolve_tab_target(call.target)
        await _check_action_guard(ctx, call, session, tab, element_text=query)
        resolved_ref = await _resolve_element(ctx, session, tab, query, element_id)
        if resolved_ref.startswith("coord:"):
            raise _ToolLogicError(
                ErrorCategory.UI_ELEMENT_DISABLED,
                "The best match was only visually located (no DOM element) — cannot type into it.",
            )
        await session.adapter.type_text(tab.tab_ref, resolved_ref, text)
        return {"tab_id": tab.tab_id}

    async def key_press(call: ToolCallRequest) -> dict:
        key = call.arguments.get("key")
        if not key:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'key' is required.")
        session, tab = m.resolve_tab_target(call.target)
        await _check_action_guard(ctx, call, session, tab, element_text=None)
        await session.adapter.press_key(tab.tab_ref, key)
        return {"tab_id": tab.tab_id}

    async def select(call: ToolCallRequest) -> dict:
        query, element_id = call.arguments.get("query"), call.arguments.get("element_id")
        value = call.arguments.get("value")
        if value is None:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'value' is required.")
        session, tab = m.resolve_tab_target(call.target)
        await _check_action_guard(ctx, call, session, tab, element_text=query)
        resolved_ref = await _resolve_element(ctx, session, tab, query, element_id)
        await session.adapter.select_option(tab.tab_ref, resolved_ref, value)
        return {"tab_id": tab.tab_id}

    async def scroll(call: ToolCallRequest) -> dict:
        direction = call.arguments.get("direction", "down")
        amount = int(call.arguments.get("amount", 600))
        session, tab = m.resolve_tab_target(call.target)
        await session.adapter.scroll(tab.tab_ref, dy=amount if direction == "down" else -amount)
        return {"tab_id": tab.tab_id}

    async def wait(call: ToolCallRequest) -> dict:
        for_what = call.arguments.get("for", "load")
        session, tab = m.resolve_tab_target(call.target)
        if for_what == "selector":
            resolved_ref = await _resolve_element(
                ctx, session, tab, call.arguments.get("query"), None
            )
            ok = await session.adapter.wait_for_selector(tab.tab_ref, resolved_ref)
        else:
            ok = await session.adapter.wait_for_load(tab.tab_ref)
        if not ok:
            raise _ToolLogicError(ErrorCategory.TIMEOUT, f"Timed out waiting for '{for_what}'.")
        return {"tab_id": tab.tab_id, "satisfied": True}

    async def screenshot(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        png_b64 = await session.adapter.screenshot_png_base64(tab.tab_ref)
        return {"tab_id": tab.tab_id, "image_base64": png_b64}

    async def upload_file(call: ToolCallRequest) -> dict:
        query, element_id = call.arguments.get("query"), call.arguments.get("element_id")
        file_path = call.arguments.get("file_path")
        if not file_path:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'file_path' is required.")
        session, tab = m.resolve_tab_target(call.target)
        await _check_action_guard(ctx, call, session, tab, element_text=query)
        resolved_ref = await _resolve_element(ctx, session, tab, query, element_id)
        await session.adapter.upload_file(tab.tab_ref, resolved_ref, file_path)
        return {"tab_id": tab.tab_id, "uploaded": file_path}

    async def download(call: ToolCallRequest) -> dict:
        url = call.arguments.get("url")
        if not url:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'url' is required.")
        validation = ctx.url_validator.validate(url)
        if not validation.allowed:
            raise _ToolLogicError(ErrorCategory.UNSAFE_URL, validation.reason)
        session, tab = m.resolve_tab_target(call.target)
        try:
            body, _content_type = await session.adapter.fetch_bytes(tab.tab_ref, url)
        except AdapterError as exc:
            raise _ToolLogicError(ErrorCategory.DOWNLOAD_FAILED, str(exc)) from exc
        filename = url.rsplit("/", 1)[-1] or "download"
        record = m.downloads.record(
            session_id=session.session_id,
            event=DownloadEvent(
                filename=filename,
                source_url=url,
                destination_path=None,
                size_bytes=len(body),
                ok=True,
            ),
        )
        return {"download_id": record.download_id, "filename": filename, "size_bytes": len(body)}

    async def download_status(call: ToolCallRequest) -> dict:
        if not call.target:
            raise _ToolLogicError(
                ErrorCategory.VALIDATION_ERROR, "A download id (target) is required."
            )
        record = m.downloads.get(call.target)
        if record is None:
            raise _ToolLogicError(
                ErrorCategory.FILE_NOT_FOUND, f"Unknown download '{call.target}'."
            )
        return {
            "download_id": record.download_id,
            "status": record.status,
            "destination_path": record.destination_path,
            "potentially_dangerous": record.is_potentially_dangerous,
        }

    async def download_open_location(call: ToolCallRequest) -> dict:
        if not call.target:
            raise _ToolLogicError(
                ErrorCategory.VALIDATION_ERROR, "A download id (target) is required."
            )
        record = m.downloads.get(call.target)
        if record is None:
            raise _ToolLogicError(
                ErrorCategory.FILE_NOT_FOUND, f"Unknown download '{call.target}'."
            )
        # brief §28 — never launches anything; only reports the path.
        return {"destination_path": record.destination_path}

    async def fill_form(call: ToolCallRequest) -> dict:
        fields = call.arguments.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise _ToolLogicError(
                ErrorCategory.VALIDATION_ERROR, "'fields' (a label->value map) is required."
            )
        for label in fields:
            if any(sensitive in label.lower() for sensitive in _SENSITIVE_FIELD_LABELS):
                raise _ToolLogicError(
                    ErrorCategory.PERMISSION_DENIED,
                    f"Refusing to auto-fill sensitive field '{label}' (brief §20: never assume "
                    "sensitive data should automatically be filled).",
                    user_action_required=True,
                )
        session, tab = m.resolve_tab_target(call.target)
        await _check_action_guard(ctx, call, session, tab, element_text=None)
        filled, skipped = [], []
        for label, value in fields.items():
            try:
                resolved_ref = await _resolve_element(ctx, session, tab, label, None)
                if resolved_ref.startswith("coord:"):
                    skipped.append(label)
                    continue
                await session.adapter.type_text(tab.tab_ref, resolved_ref, str(value))
                filled.append(label)
            except _ToolLogicError:
                skipped.append(label)
        return {"tab_id": tab.tab_id, "filled": filled, "skipped": skipped}

    async def clipboard_read(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        return {"text": ctx.redactor.redact(await session.adapter.clipboard_read(tab.tab_ref))}

    async def clipboard_write(call: ToolCallRequest) -> dict:
        session, tab = m.resolve_tab_target(call.target)
        await session.adapter.clipboard_write(tab.tab_ref, call.arguments.get("text", ""))
        return {"tab_id": tab.tab_id}

    async def web_research(call: ToolCallRequest) -> dict:
        goal = call.arguments.get("goal")
        if not goal:
            raise _ToolLogicError(ErrorCategory.VALIDATION_ERROR, "'goal' is required.")
        try:
            result = await ctx.research.run(
                goal=goal,
                max_sites=int(call.arguments.get("max_sites", 3)),
                max_tabs=int(call.arguments.get("max_tabs", 3)),
                max_steps=int(call.arguments.get("max_steps", 12)),
                max_time_seconds=float(call.arguments.get("max_time_seconds", 60)),
            )
        except ResearchBudgetExceeded as exc:
            raise _ToolLogicError(ErrorCategory.TIMEOUT, str(exc)) from exc
        return result.model_dump()

    empty_schema = {"type": "object", "properties": {}}

    tools: list[tuple[ToolDefinition, Callable]] = [
        (
            _def(
                "browser.launch",
                "Launch Browser",
                "Launch a new sandboxed Chromium browser session.",
                input_schema={"type": "object", "properties": {"headless": {"type": "boolean"}}},
                risk_level=RiskLevel.SAFE,
                keywords=["browser", "chrome", "open browser", "launch"],
            ),
            launch,
        ),
        (
            _def(
                "browser.close",
                "Close Browser",
                "Close a browser session and all its tabs.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["close browser"],
            ),
            close,
        ),
        (
            _def(
                "browser.focus",
                "Focus Browser Session",
                "Make a browser session the active target for tools.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["focus browser"],
            ),
            focus,
        ),
        (
            _def(
                "browser.new_tab",
                "New Tab",
                "Open a new browser tab, optionally navigating to a URL.",
                input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
                risk_level=RiskLevel.SAFE,
                keywords=["new tab", "open tab"],
            ),
            new_tab,
        ),
        (
            _def(
                "browser.close_tab",
                "Close Tab",
                "Close a browser tab.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["close tab"],
            ),
            close_tab,
        ),
        (
            _def(
                "browser.list_tabs",
                "List Tabs",
                "List every open tab in a browser session.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["list tabs", "tabs"],
            ),
            list_tabs,
        ),
        (
            _def(
                "browser.switch_tab",
                "Switch Tab",
                "Make a tab the active tab.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["switch tab"],
            ),
            switch_tab,
        ),
        (
            _def(
                "browser.current_tab",
                "Current Tab",
                "Get the currently active tab.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["current tab"],
            ),
            current_tab,
        ),
        (
            _def(
                "browser.find_tab",
                "Find Tab",
                "Find an already-open tab by title/URL/domain substring.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                risk_level=RiskLevel.SAFE,
                keywords=["find tab", "which tab"],
            ),
            find_tab,
        ),
        (
            _def(
                "browser.navigate",
                "Navigate",
                "Navigate a tab to a URL.",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                risk_level=RiskLevel.SAFE,
                keywords=["navigate", "go to", "open url"],
            ),
            navigate,
        ),
        (
            _def(
                "browser.back",
                "Back",
                "Navigate back in tab history.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["back", "go back"],
            ),
            back,
        ),
        (
            _def(
                "browser.forward",
                "Forward",
                "Navigate forward in tab history.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["forward"],
            ),
            forward,
        ),
        (
            _def(
                "browser.reload",
                "Reload",
                "Reload the current page.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["reload", "refresh"],
            ),
            reload,
        ),
        (
            _def(
                "browser.stop_loading",
                "Stop Loading",
                "Stop the current page load.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["stop loading"],
            ),
            stop_loading,
        ),
        (
            _def(
                "browser.search",
                "Search",
                "Search the web via a configured search engine.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "engine": {"type": "string"}},
                    "required": ["query"],
                },
                risk_level=RiskLevel.SAFE,
                keywords=["search", "google", "bing", "duckduckgo"],
            ),
            search,
        ),
        (
            _def(
                "browser.get_page",
                "Get Page",
                "Get a compact semantic observation of the current page.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["observe page", "page state"],
            ),
            get_page,
        ),
        (
            _def(
                "browser.get_elements",
                "Get Elements",
                "List interactive elements on the current page.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["elements", "buttons", "links"],
            ),
            get_elements,
        ),
        (
            _def(
                "browser.extract_text",
                "Extract Text",
                "Extract visible page text (sanitized, tagged untrusted).",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["extract text", "read page"],
            ),
            extract_text,
        ),
        (
            _def(
                "browser.find",
                "Find on Page",
                "Find an element on the page by text/semantic meaning/role.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                risk_level=RiskLevel.SAFE,
                keywords=["find", "locate element"],
            ),
            find,
        ),
        (
            _def(
                "browser.click",
                "Click",
                "Click an element (resolved by query, element_id, or coordinates).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "element_id": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                },
                risk_level=RiskLevel.MODERATE,
                confirmation=ConfirmationPolicy.SESSION,
                keywords=["click", "press button", "tap"],
            ),
            click,
        ),
        (
            _def(
                "browser.type",
                "Type",
                "Type text into a resolved input element.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "element_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["text"],
                },
                risk_level=RiskLevel.MODERATE,
                confirmation=ConfirmationPolicy.SESSION,
                keywords=["type", "fill input", "enter text"],
            ),
            type_text,
        ),
        (
            _def(
                "browser.key_press",
                "Key Press",
                "Send a keyboard key (Enter, Escape, Tab, arrows, etc).",
                input_schema={
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                },
                risk_level=RiskLevel.MODERATE,
                keywords=["press key", "enter", "escape", "tab"],
            ),
            key_press,
        ),
        (
            _def(
                "browser.select",
                "Select",
                "Choose an option in a resolved <select> element.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "element_id": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["value"],
                },
                risk_level=RiskLevel.MODERATE,
                keywords=["select", "dropdown", "choose option"],
            ),
            select,
        ),
        (
            _def(
                "browser.scroll",
                "Scroll",
                "Scroll the page.",
                input_schema={
                    "type": "object",
                    "properties": {"direction": {"type": "string"}, "amount": {"type": "integer"}},
                },
                risk_level=RiskLevel.SAFE,
                keywords=["scroll"],
            ),
            scroll,
        ),
        (
            _def(
                "browser.wait",
                "Wait",
                "Wait for page load or an element to appear.",
                input_schema={
                    "type": "object",
                    "properties": {"for": {"type": "string"}, "query": {"type": "string"}},
                },
                risk_level=RiskLevel.SAFE,
                keywords=["wait"],
            ),
            wait,
        ),
        (
            _def(
                "browser.screenshot",
                "Screenshot",
                "Capture a screenshot of the current tab.",
                input_schema=empty_schema,
                risk_level=RiskLevel.MODERATE,
                keywords=["screenshot"],
            ),
            screenshot,
        ),
        (
            _def(
                "browser.upload_file",
                "Upload File",
                "Upload a local file into a resolved file-input element.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "element_id": {"type": "string"},
                        "file_path": {"type": "string"},
                    },
                    "required": ["file_path"],
                },
                risk_level=RiskLevel.SENSITIVE,
                confirmation=ConfirmationPolicy.ALWAYS,
                keywords=["upload", "attach file"],
            ),
            upload_file,
        ),
        (
            _def(
                "browser.download",
                "Download",
                "Fetch a URL's bytes as a tracked download.",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
                risk_level=RiskLevel.MODERATE,
                keywords=["download", "save file", "get pdf"],
            ),
            download,
        ),
        (
            _def(
                "download.list",
                "List Downloads",
                "List tracked downloads.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["downloads", "list downloads"],
            ),
            download_list,
        ),
        (
            _def(
                "download.status",
                "Download Status",
                "Get one download's status.",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["download status"],
            ),
            download_status,
        ),
        (
            _def(
                "download.open_location",
                "Download Location",
                "Report a download's destination path (never launches anything).",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["open download location"],
            ),
            download_open_location,
        ),
        (
            _def(
                "browser.fill_form",
                "Fill Form",
                "Fill a non-sensitive form from a label->value map.",
                input_schema={
                    "type": "object",
                    "properties": {"fields": {"type": "object"}},
                    "required": ["fields"],
                },
                risk_level=RiskLevel.MODERATE,
                confirmation=ConfirmationPolicy.SESSION,
                keywords=["fill form", "form"],
            ),
            fill_form,
        ),
        (
            _def(
                "browser.clipboard_read",
                "Clipboard Read",
                "Read the browser clipboard (secrets redacted).",
                input_schema=empty_schema,
                risk_level=RiskLevel.SAFE,
                keywords=["clipboard", "paste"],
            ),
            clipboard_read,
        ),
        (
            _def(
                "browser.clipboard_write",
                "Clipboard Write",
                "Write text to the browser clipboard.",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                risk_level=RiskLevel.MODERATE,
                keywords=["clipboard", "copy"],
            ),
            clipboard_write,
        ),
        (
            _def(
                "web.research",
                "Web Research",
                "Bounded multi-step search/extract/compare/synthesize research task.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "max_sites": {"type": "integer"},
                        "max_tabs": {"type": "integer"},
                        "max_steps": {"type": "integer"},
                        "max_time_seconds": {"type": "number"},
                    },
                    "required": ["goal"],
                },
                risk_level=RiskLevel.MODERATE,
                keywords=["research", "compare", "look up", "summarize web"],
            ),
            web_research,
        ),
    ]

    return [(definition, _browser_executor(definition.id, fn)) for definition, fn in tools]
