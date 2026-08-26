"""Short-lived observation cache. docs/phase-3 §30: 'no unlimited
screenshot history' — every entry expires after `ttl_seconds` and the
cache is capped at `max_entries`, evicting the oldest entry rather than
growing unbounded. Pure Python, no persistence, genuinely tested here.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class _Entry:
    value: object
    image_base64: str | None
    expires_at: float


@dataclass
class ObservationCache:
    ttl_seconds: float = 60.0
    max_entries: int = 20
    _entries: dict[str, _Entry] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def put(self, value: object, *, image_base64: str | None = None) -> str:
        self._purge_expired()
        ref = uuid.uuid4().hex
        self._entries[ref] = _Entry(
            value=value, image_base64=image_base64, expires_at=time.monotonic() + self.ttl_seconds
        )
        self._order.append(ref)
        while len(self._order) > self.max_entries:
            oldest = self._order.pop(0)
            self._entries.pop(oldest, None)
        return ref

    def get(self, ref: str) -> tuple[object, str | None] | None:
        self._purge_expired()
        entry = self._entries.get(ref)
        if entry is None:
            return None
        return entry.value, entry.image_base64

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [ref for ref, entry in self._entries.items() if entry.expires_at <= now]
        for ref in expired:
            self._entries.pop(ref, None)
            if ref in self._order:
                self._order.remove(ref)

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._entries)
