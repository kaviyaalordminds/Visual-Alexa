"""docs/phase-5/OFFLINE-MODE.md, brief §56-57 — cloud features only ever
proceed on a confirmed ONLINE check; anything else (OFFLINE/LIMITED/
UNKNOWN/a raising checker) means "don't attempt it, say so honestly"."""

from __future__ import annotations

from voice.core.connectivity import ConnectivityManager
from voice.core.enums import ConnectivityState


def test_online_checker_reports_online_and_allows_cloud():
    manager = ConnectivityManager(checker=lambda: True)
    assert manager.check() == ConnectivityState.ONLINE
    assert manager.cloud_features_available() is True


def test_offline_checker_reports_offline_and_blocks_cloud():
    manager = ConnectivityManager(checker=lambda: False)
    assert manager.check() == ConnectivityState.OFFLINE
    assert manager.cloud_features_available() is False


def test_no_checker_is_unknown_not_assumed_online():
    manager = ConnectivityManager()
    assert manager.check() == ConnectivityState.UNKNOWN
    assert manager.cloud_features_available() is False


def test_raising_checker_is_unknown_never_crashes_the_caller():
    def _boom() -> bool:
        raise RuntimeError("network probe failed")

    manager = ConnectivityManager(checker=_boom)
    assert manager.check() == ConnectivityState.UNKNOWN
    assert manager.cloud_features_available() is False


def test_last_known_state_tracks_the_most_recent_check():
    manager = ConnectivityManager(checker=lambda: True)
    assert manager.last_known_state == ConnectivityState.UNKNOWN
    manager.check()
    assert manager.last_known_state == ConnectivityState.ONLINE
