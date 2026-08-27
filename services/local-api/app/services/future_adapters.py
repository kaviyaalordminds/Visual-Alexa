"""Interface-only stubs for capabilities explicitly out of this phase's
scope. brief §45/§51/§134-136, §176 (Stop Condition): "Prepare... do not
implement." Each class exists only so a future phase has a concrete
extension point to implement against — none is registered, imported by
`main.py`, or reachable from any tool/HTTP route. Every method raises
`NotImplementedError`.
"""

from __future__ import annotations

from typing import Any


class MatterAdapter:
    """docs/architecture/10-IOT.md §3 — a future `DeviceGatewayAdapter`
    for the Matter (Connectivity Standards Alliance) protocol. Not
    implemented — brief §134: 'prepare... but do not implement the full
    Matter stack unless required.'"""

    async def discover(self) -> list[Any]:
        raise NotImplementedError

    async def pair(self, device_id: str) -> Any:
        raise NotImplementedError

    async def send_command(self, device_id: str, capability_key: str, value: Any) -> Any:
        raise NotImplementedError


class HomeAssistantAdapter:
    """Brief §135: 'prepare... but do not connect automatically.' Not
    implemented, no default Home Assistant instance is ever assumed or
    contacted."""

    async def discover(self) -> list[Any]:
        raise NotImplementedError

    async def pair(self, device_id: str) -> Any:
        raise NotImplementedError

    async def send_command(self, device_id: str, capability_key: str, value: Any) -> Any:
        raise NotImplementedError


class RemoteDeviceAdapter:
    """Brief §51/§136/§167 — 'no remote-PC capability in Phase 7...
    architecture may define RemoteDevice but it must remain disabled.'
    `ENABLED` is intentionally not a real attribute anyone can flip —
    the class has no state at all, only a constant documenting the
    default every future implementation must preserve."""

    DISABLED_BY_DEFAULT = True

    async def discover(self) -> list[Any]:
        raise NotImplementedError

    async def connect(self, device_id: str) -> Any:
        raise NotImplementedError
