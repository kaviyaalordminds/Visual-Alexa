"""docs/phase-3 §30 — 'no unlimited screenshot history': bounded size, TTL
expiry."""

from __future__ import annotations

import time

from vision.core.cache import ObservationCache


def test_put_and_get_round_trips():
    cache = ObservationCache(ttl_seconds=60, max_entries=5)
    ref = cache.put({"a": 1}, image_base64="abc")
    value, image = cache.get(ref)
    assert value == {"a": 1}
    assert image == "abc"


def test_unknown_ref_returns_none():
    cache = ObservationCache()
    assert cache.get("does-not-exist") is None


def test_expired_entry_is_purged():
    cache = ObservationCache(ttl_seconds=0.05, max_entries=5)
    ref = cache.put({"a": 1})
    time.sleep(0.1)
    assert cache.get(ref) is None


def test_max_entries_evicts_oldest():
    cache = ObservationCache(ttl_seconds=60, max_entries=2)
    ref1 = cache.put("first")
    cache.put("second")
    cache.put("third")
    assert cache.get(ref1) is None
    assert len(cache) == 2
