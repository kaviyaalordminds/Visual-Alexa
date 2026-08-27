"""brief §134-136 — interface-only stubs, never wired to anything real.
See docs/phase-7/DEVICE-PAIRING.md §6, docs/architecture/10-IOT.md."""

from __future__ import annotations

import pytest
from app.services.future_adapters import HomeAssistantAdapter, MatterAdapter, RemoteDeviceAdapter


async def test_matter_adapter_is_not_implemented():
    with pytest.raises(NotImplementedError):
        await MatterAdapter().discover()


async def test_home_assistant_adapter_is_not_implemented():
    with pytest.raises(NotImplementedError):
        await HomeAssistantAdapter().discover()


async def test_remote_device_adapter_is_not_implemented():
    with pytest.raises(NotImplementedError):
        await RemoteDeviceAdapter().discover()


def test_remote_device_adapter_is_disabled_by_default():
    assert RemoteDeviceAdapter.DISABLED_BY_DEFAULT is True


def test_none_of_these_adapters_are_imported_by_main():
    import ast
    from pathlib import Path

    main_source = (Path(__file__).parents[2] / "services/local-api/app/main.py").read_text()
    tree = ast.parse(main_source)
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "MatterAdapter" not in imported_names
    assert "HomeAssistantAdapter" not in imported_names
    assert "RemoteDeviceAdapter" not in imported_names
