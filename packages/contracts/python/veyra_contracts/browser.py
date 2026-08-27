"""Browser & Web Intelligence contracts. docs/phase-8/BROWSER-ARCHITECTURE.md.

Mirrors the shapes `docs/architecture/11-INTEGRATIONS.md`-style contracts
already establish: typed data crossing the service boundary (API
responses, extension-bridge payloads), never behavior. Behavior lives in
`app/services/browser/*` — CLAUDE.md's own rule for this repo.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from veyra_contracts.enums import DomainTrustStatus, EvidenceTier


class BrowserTabInfo(BaseModel):
    """docs/phase-8/TAB-MANAGEMENT.md §6."""

    tab_id: str
    title: str
    url: str
    domain: str
    status: str = Field(description="'loading' | 'complete' | 'crashed' | 'closed'")
    active: bool
    favicon: str | None = None


class BrowserSessionInfo(BaseModel):
    """docs/phase-8/BROWSER-SESSION.md §5."""

    session_id: str
    browser_type: str
    connection_status: str
    created_at: str
    last_activity: str
    tabs: list[BrowserTabInfo] = Field(default_factory=list)
    active_tab_id: str | None = None


class BrowserElementInfo(BaseModel):
    """docs/phase-8/ELEMENT-RESOLUTION.md §12 — a resolved element's
    semantic identity, never only x/y (brief §60: 'An element should have
    semantic identity, not only x=521 y=384')."""

    element_id: str
    role: str | None = None
    tag: str | None = None
    text: str | None = None
    aria_label: str | None = None
    placeholder: str | None = None
    name: str | None = None
    visible: bool = True
    enabled: bool = True
    bounding_box: dict[str, float] | None = None
    selector: str | None = None
    semantic_description: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_tier: EvidenceTier


class PageObservation(BaseModel):
    """docs/phase-8/PAGE-OBSERVATION.md §10-11 — the compact semantic
    representation sent to the planner, never the raw page (brief §10:
    'Do NOT send the entire page blindly to an LLM.')."""

    url: str
    title: str
    domain: str
    dom_summary: list[str] = Field(
        default_factory=list, description="Indented outline lines, e.g. 'Header > Search input'."
    )
    interactive_elements: list[BrowserElementInfo] = Field(default_factory=list)
    visible_text_excerpt: str = ""
    login_state: str = Field(default="UNKNOWN", description="LOGGED_IN|LOGGED_OUT|UNKNOWN")
    captcha_detected: bool = False
    otp_detected: bool = False
    payment_page_detected: bool = False
    domain_trust: DomainTrustStatus = DomainTrustStatus.UNKNOWN


class ResearchSource(BaseModel):
    """docs/phase-8/WEB-RESEARCH.md §32/§101."""

    url: str
    domain: str
    title: str
    retrieved_content: str
    retrieved_at: str
    quality: str = Field(
        default="unknown", description="official|primary|secondary|community|unknown"
    )


class ResearchResult(BaseModel):
    """docs/phase-8/WEB-COMPARISON.md §107 — normalized comparison output."""

    goal: str
    sources: list[ResearchSource] = Field(default_factory=list)
    normalized_fields: dict[str, Any] = Field(default_factory=dict)
    differences: list[str] = Field(default_factory=list)
    similarities: list[str] = Field(default_factory=list)
    summary: str = ""


class ExtensionCommandRequest(BaseModel):
    """docs/phase-8/EXTENSION-BRIDGE.md §74 — the closed set of commands
    the extension bridge accepts; no `execute_arbitrary_command` exists
    anywhere in this shape."""

    command: str
    tab_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
