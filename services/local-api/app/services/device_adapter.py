"""DeviceAdapter — the seam a future concrete IoT protocol implementation
(Matter, Home Assistant, a manufacturer API, local-network discovery)
plugs into. docs/subsystem-activation/IOT-STATUS.md.

This module ships the `Protocol` only — no concrete adapter. Matches the
same pattern already established by `LLMProvider`/`VisionProvider`/voice's
provider `Protocol`s: define the interface now, so a real implementation
in a future phase is a new adapter module, not a rearchitecture, but never
ship a fake/stub implementation pretending to be a real integration
(CLAUDE.md's Phase 8 Stop Condition; the task's own "do not create fake
IoT integrations" instruction). The only device capability this build
actually controls is the mock AC in `app/services/mock_iot.py`, which
talks to `DevicePairingService` directly and does not use this Protocol —
it is intentionally simple enough not to need it.

Device identity, pairing, authentication, authorization, and the runtime
permission cache are already real and implemented in
`app/services/device_pairing.py` (`DevicePairingService`) — a
`DeviceAdapter` is the *next* stage after CONTROL is authorized: how a
command actually reaches the physical/network device, which is protocol-
specific and does not exist for any real protocol yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DiscoveredDevice:
    """What a `DeviceAdapter.discover()` call reports about a device it
    found on the network/bus it's responsible for — informational only;
    discovery never implies pairing or control access."""

    external_id: str
    name: str
    manufacturer: str | None
    protocol: str


@dataclass(frozen=True)
class DeviceCommandResult:
    success: bool
    reason: str | None = None


class DeviceAdapter(Protocol):
    """One adapter per protocol (`protocol_id`, e.g. `"matter"`,
    `"home_assistant"`, `"local_network"`). Every method here is only ever
    called for a device that has already completed the full
    PAIR -> IDENTIFY -> AUTHENTICATE -> AUTHORIZE -> REGISTER_CAPABILITIES
    lifecycle in `DevicePairingService` — an adapter has no independent
    authority to control a device VEYRA hasn't already authorized."""

    protocol_id: str

    async def discover(self) -> list[DiscoveredDevice]: ...

    async def connect(self, external_id: str, credentials: dict[str, str]) -> bool: ...

    async def send_command(
        self, external_id: str, capability_key: str, command: dict[str, object]
    ) -> DeviceCommandResult: ...

    async def disconnect(self, external_id: str) -> None: ...
