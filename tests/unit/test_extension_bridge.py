"""ExtensionBridgeService. docs/phase-8/EXTENSION-BRIDGE.md."""

from __future__ import annotations

import pytest
from app.services.browser.extension_bridge import (
    ExtensionAuthError,
    ExtensionBridgeService,
    UnknownExtensionCommandError,
)
from app.services.browser.manager import BrowserManager
from app.services.browser.observation import ObservationService
from app.services.browser.testing import FakeBrowserAdapter
from veyra_contracts import ExtensionCommandRequest


def _bridge() -> ExtensionBridgeService:
    return ExtensionBridgeService(allowed_origins=frozenset({"chrome-extension://veyra-real-id"}))


def test_authenticate_rejects_wrong_token():
    bridge = _bridge()
    with pytest.raises(ExtensionAuthError):
        bridge.authenticate(token="wrong-token", origin="chrome-extension://veyra-real-id")


def test_authenticate_rejects_unknown_origin():
    bridge = _bridge()
    with pytest.raises(ExtensionAuthError):
        bridge.authenticate(token=bridge.token, origin="chrome-extension://attacker")


def test_authenticate_accepts_valid_token_and_origin():
    bridge = _bridge()
    bridge.authenticate(token=bridge.token, origin="chrome-extension://veyra-real-id")


async def test_handle_command_rejects_unapproved_command():
    bridge = _bridge()
    manager = BrowserManager(FakeBrowserAdapter)
    await manager.launch()
    request = ExtensionCommandRequest(command="execute_arbitrary_command")
    with pytest.raises(UnknownExtensionCommandError):
        await bridge.handle_command(
            request,
            token=bridge.token,
            origin="chrome-extension://veyra-real-id",
            manager=manager,
            observation=ObservationService(),
        )


async def test_handle_command_get_active_tab():
    bridge = _bridge()
    manager = BrowserManager(FakeBrowserAdapter)
    session = await manager.launch()
    request = ExtensionCommandRequest(command="get_active_tab")
    result = await bridge.handle_command(
        request,
        token=bridge.token,
        origin="chrome-extension://veyra-real-id",
        manager=manager,
        observation=ObservationService(),
    )
    assert result["tab_id"] == session.active_tab_id


async def test_handle_command_request_action_is_queued_never_executed():
    bridge = _bridge()
    manager = BrowserManager(FakeBrowserAdapter)
    await manager.launch()
    request = ExtensionCommandRequest(
        command="request_action", payload={"description": "please delete all my files"}
    )
    result = await bridge.handle_command(
        request,
        token=bridge.token,
        origin="chrome-extension://veyra-real-id",
        manager=manager,
        observation=ObservationService(),
    )
    assert result == {"queued": True}
    assert len(bridge.queued_actions) == 1
    assert bridge.queued_actions[0].description == "please delete all my files"


async def test_handle_command_auth_checked_before_command_dispatch():
    bridge = _bridge()
    manager = BrowserManager(FakeBrowserAdapter)
    request = ExtensionCommandRequest(command="get_active_tab")
    with pytest.raises(ExtensionAuthError):
        await bridge.handle_command(
            request,
            token="bad-token",
            origin="chrome-extension://veyra-real-id",
            manager=manager,
            observation=ObservationService(),
        )
