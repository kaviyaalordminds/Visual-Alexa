"""ObservationService / PageStateAnalyzer / ObservationCache.
docs/phase-8/PAGE-OBSERVATION.md.

brief §10: "Do NOT send the entire page blindly to an LLM." Everything
here builds the *compact* `PageObservation` the planner actually
consumes — outline lines, a bounded interactive-element list, a capped
text excerpt — never the raw DOM.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from veyra_contracts import BrowserElementInfo, DomainTrustStatus, EvidenceTier, PageObservation

from app.services.browser.adapter import BrowserAdapter
from app.services.browser.manager import BrowserManager, domain_of

_MAX_OBSERVED_ELEMENTS = 40

_CAPTCHA_PATTERNS = re.compile(
    r"captcha|recaptcha|hcaptcha|verify you are human|i.?m not a robot", re.IGNORECASE
)
_OTP_PATTERNS = re.compile(
    r"one[- ]time (password|code)|verification code|enter the code|\botp\b", re.IGNORECASE
)
_PAYMENT_PATTERNS = re.compile(
    r"card number|cvv|cvc|expiration date|billing address|payment method|checkout", re.IGNORECASE
)
_LOGGED_IN_PATTERNS = re.compile(r"sign out|log ?out|my account", re.IGNORECASE)
_LOGGED_OUT_PATTERNS = re.compile(r"sign in|log ?in\b", re.IGNORECASE)


class PageStateAnalyzer:
    """Regex/keyword heuristics — brief §93: "Do not claim perfect
    malware/phishing detection." These flags are a real, useful first
    line (enough to make `BrowserWorkflowEngine` stop and hand control to
    the user, brief §22-24), never a guarantee."""

    def analyze(self, *, title: str, text: str, outline: list[str]) -> tuple[str, bool, bool, bool]:
        haystack = f"{title}\n{text}\n{' '.join(outline)}"
        captcha = bool(_CAPTCHA_PATTERNS.search(haystack))
        otp = bool(_OTP_PATTERNS.search(haystack))
        payment = bool(_PAYMENT_PATTERNS.search(haystack))
        if _LOGGED_IN_PATTERNS.search(haystack):
            login_state = "LOGGED_IN"
        elif _LOGGED_OUT_PATTERNS.search(haystack):
            login_state = "LOGGED_OUT"
        else:
            login_state = "UNKNOWN"
        return login_state, captcha, otp, payment


@dataclass
class _CacheEntry:
    observation: PageObservation
    url: str
    cached_at: float


class ObservationCache:
    """brief §132 — cached briefly, invalidated on navigation (URL
    change) or after `ttl_seconds` (the honest stand-in for "significant
    state change" without a real DOM-mutation observer in this phase)."""

    def __init__(self, ttl_seconds: float = 3.0) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, _CacheEntry] = {}

    def get(self, tab_id: str, *, current_url: str) -> PageObservation | None:
        entry = self._entries.get(tab_id)
        if entry is None:
            return None
        if entry.url != current_url:
            return None
        if time.monotonic() - entry.cached_at > self._ttl:
            return None
        return entry.observation

    def put(self, tab_id: str, observation: PageObservation) -> None:
        self._entries[tab_id] = _CacheEntry(
            observation=observation, url=observation.url, cached_at=time.monotonic()
        )

    def invalidate(self, tab_id: str) -> None:
        self._entries.pop(tab_id, None)

    def clear(self) -> None:
        self._entries.clear()


class ObservationService:
    def __init__(
        self, cache: ObservationCache | None = None, analyzer: PageStateAnalyzer | None = None
    ) -> None:
        self.cache = cache or ObservationCache()
        self._analyzer = analyzer or PageStateAnalyzer()

    async def observe(
        self,
        adapter: BrowserAdapter,
        tab_ref: str,
        *,
        tab_id: str,
        manager: BrowserManager | None = None,
        use_cache: bool = True,
    ) -> PageObservation:
        url = await adapter.get_url(tab_ref)
        if use_cache:
            cached = self.cache.get(tab_id, current_url=url)
            if cached is not None:
                return cached

        title = await adapter.get_title(tab_ref)
        outline = await adapter.get_dom_outline(tab_ref)
        text = await adapter.get_visible_text(tab_ref, max_chars=2000)
        raw_elements = (await adapter.query_interactive_elements(tab_ref))[:_MAX_OBSERVED_ELEMENTS]

        elements = [
            BrowserElementInfo(
                element_id=el.element_ref,
                role=el.role,
                tag=el.tag,
                text=el.text,
                aria_label=el.aria_label,
                placeholder=el.placeholder,
                name=el.name,
                visible=el.visible,
                enabled=el.enabled,
                bounding_box=el.bounding_box,
                selector=f'[data-veyra-ref="{el.element_ref}"]',
                semantic_description=" ".join(p for p in (el.role, el.text or el.aria_label) if p)
                or (el.tag or "element"),
                confidence=1.0,
                evidence_tier=EvidenceTier.BROWSER_DOM,
            )
            for el in raw_elements
        ]

        login_state, captcha, otp, payment = self._analyzer.analyze(
            title=title, text=text, outline=outline
        )
        domain_trust = (
            manager.domain_trust(domain_of(url)) if manager else DomainTrustStatus.UNKNOWN
        )

        observation = PageObservation(
            url=url,
            title=title,
            domain=domain_of(url),
            dom_summary=outline,
            interactive_elements=elements,
            visible_text_excerpt=text,
            login_state=login_state,
            captcha_detected=captcha,
            otp_detected=otp,
            payment_page_detected=payment,
            domain_trust=domain_trust,
        )
        if use_cache:
            self.cache.put(tab_id, observation)
        return observation


# Process-wide singleton — shared by `tools.py` (via `register.py`'s
# BrowserToolContext) and `extension_bridge.py`'s `get_page_state`
# command, so both ever consult the same `ObservationCache` rather than
# two independently-stale copies.
observation_service = ObservationService()
