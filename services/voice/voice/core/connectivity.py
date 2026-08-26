"""ConnectivityManager — tracks whether cloud-dependent voice features are
usable right now. docs/phase-5/OFFLINE-MODE.md, brief §56-57.

The actual "are we online" check is injected (a callable) rather than
performed here — this module has no network access itself, matching every
other Phase 5 core module's no-I/O discipline. `app/services/voice` wires
a real check (e.g. a lightweight reachability probe) in; tests inject a
canned one via `set_checker`/direct construction.
"""

from __future__ import annotations

from collections.abc import Callable

from voice.core.enums import ConnectivityState


class ConnectivityManager:
    """docs/phase-5 §56. `checker` returns True (online), False (offline),
    or raises (treated as UNKNOWN, never silently assumed online)."""

    def __init__(self, checker: Callable[[], bool] | None = None) -> None:
        self._checker = checker
        self._last_state: ConnectivityState = ConnectivityState.UNKNOWN

    def check(self) -> ConnectivityState:
        if self._checker is None:
            self._last_state = ConnectivityState.UNKNOWN
            return self._last_state
        try:
            online = self._checker()
        except Exception:
            self._last_state = ConnectivityState.UNKNOWN
            return self._last_state
        self._last_state = ConnectivityState.ONLINE if online else ConnectivityState.OFFLINE
        return self._last_state

    @property
    def last_known_state(self) -> ConnectivityState:
        return self._last_state

    def cloud_features_available(self) -> bool:
        """docs/phase-5 §57 — a cloud-only feature may only proceed when
        connectivity is confirmed ONLINE; OFFLINE, LIMITED, and UNKNOWN all
        mean "do not attempt it, say so honestly" instead of guessing."""
        return self.check() == ConnectivityState.ONLINE
