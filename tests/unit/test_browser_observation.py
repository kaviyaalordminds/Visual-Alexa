"""ObservationService / PageStateAnalyzer / ObservationCache.
docs/phase-8/PAGE-OBSERVATION.md."""

from __future__ import annotations

from app.services.browser.adapter import RawElement
from app.services.browser.observation import ObservationService, PageStateAnalyzer
from app.services.browser.testing import FakeBrowserAdapter, FakePage


def test_analyzer_detects_captcha():
    _login_state, captcha, otp, _payment = PageStateAnalyzer().analyze(
        title="Verify", text="Please complete the CAPTCHA to continue.", outline=[]
    )
    assert captcha
    assert not otp


def test_analyzer_detects_otp():
    _, captcha, otp, _ = PageStateAnalyzer().analyze(
        title="Verify", text="Enter the verification code sent to your phone.", outline=[]
    )
    assert otp
    assert not captcha


def test_analyzer_detects_payment_page():
    *_rest, payment = PageStateAnalyzer().analyze(
        title="Checkout", text="Enter your card number and CVV to complete checkout.", outline=[]
    )
    assert payment


def test_analyzer_detects_logged_in_state():
    login_state, *_ = PageStateAnalyzer().analyze(
        title="Home", text="Sign out | My Account", outline=[]
    )
    assert login_state == "LOGGED_IN"


def test_analyzer_detects_logged_out_state():
    login_state, *_ = PageStateAnalyzer().analyze(title="Home", text="Please sign in", outline=[])
    assert login_state == "LOGGED_OUT"


def test_analyzer_normal_page_flags_nothing():
    login_state, captcha, otp, payment = PageStateAnalyzer().analyze(
        title="Blog", text="This is a normal article about gardening.", outline=[]
    )
    assert not captcha and not otp and not payment
    assert login_state == "UNKNOWN"


async def test_observation_service_builds_compact_page_observation():
    adapter = FakeBrowserAdapter()
    adapter.add_page(
        "https://x/",
        FakePage(
            title="Test Page",
            text="Welcome to the test page.",
            outline=["header", "main"],
            elements=[
                RawElement(
                    element_ref="1",
                    role="button",
                    tag="button",
                    text="Download",
                    aria_label=None,
                    placeholder=None,
                    name=None,
                    value=None,
                    visible=True,
                    enabled=True,
                    bounding_box={"x": 0, "y": 0, "width": 10, "height": 10},
                )
            ],
        ),
    )
    tab_ref = await adapter.new_tab(url="https://x/")
    service = ObservationService()
    observation = await service.observe(adapter, tab_ref, tab_id="tab-1", use_cache=False)
    assert observation.title == "Test Page"
    assert observation.domain == "x"
    assert len(observation.interactive_elements) == 1
    assert not observation.captcha_detected


async def test_observation_cache_reused_for_same_url():
    adapter = FakeBrowserAdapter()
    adapter.add_page("https://x/", FakePage(title="Cached Page"))
    tab_ref = await adapter.new_tab(url="https://x/")
    service = ObservationService()
    first = await service.observe(adapter, tab_ref, tab_id="tab-1")
    # mutate the underlying page without invalidating the cache manually —
    # a cached read for the same URL should still return the old snapshot.
    adapter.pages["https://x/"].title = "Changed"
    second = await service.observe(adapter, tab_ref, tab_id="tab-1")
    assert first.title == second.title == "Cached Page"


async def test_observation_cache_invalidated_by_navigation():
    adapter = FakeBrowserAdapter()
    adapter.add_page("https://x/a", FakePage(title="Page A"))
    adapter.add_page("https://x/b", FakePage(title="Page B"))
    tab_ref = await adapter.new_tab(url="https://x/a")
    service = ObservationService()
    first = await service.observe(adapter, tab_ref, tab_id="tab-1")
    await adapter.navigate(tab_ref, "https://x/b")
    second = await service.observe(adapter, tab_ref, tab_id="tab-1")
    assert first.title == "Page A"
    assert second.title == "Page B"
