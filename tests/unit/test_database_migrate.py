"""app.db.migrate — real Alembic migrations applied against real,
isolated SQLite files (never the shared conftest.py test database, which
deliberately uses a different, faster `Base.metadata.create_all()`
strategy — see conftest.py's own docstring). Proves the actual bug this
module fixes: a fresh or stale database reaching a correct, head-revision
schema without ever losing existing data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from app.core.config import Settings
from app.db.migrate import (
    DatabaseInitializationError,
    _build_alembic_config,
    _sync_db_url,
    current_revision,
    ensure_database_ready,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _settings_for(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{db_path}",
        secret_key="test-only-secret",
    )


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "veyra-test.db"


def test_current_revision_is_none_for_a_nonexistent_database(tmp_db_path):
    settings = _settings_for(tmp_db_path)
    assert not tmp_db_path.exists()
    assert current_revision(settings) is None


def test_fresh_database_is_created_and_migrated_to_head(tmp_db_path):
    settings = _settings_for(tmp_db_path)
    revision = ensure_database_ready(settings)

    assert tmp_db_path.exists()
    assert revision == current_revision(settings)

    con = sqlite3.connect(tmp_db_path)
    try:
        tables = {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        con.close()
    # The exact table this bug report's traceback failed on, plus a
    # representative sample of tables added by later migrations (proving
    # the *whole* chain ran, not just the first migration).
    assert "applications" in tables
    assert "plugins" in tables
    assert "plugin_permissions" in tables
    assert "alembic_version" in tables


def test_ensure_database_ready_is_idempotent(tmp_db_path):
    settings = _settings_for(tmp_db_path)
    first = ensure_database_ready(settings)
    second = ensure_database_ready(settings)
    assert first == second


def test_stale_database_is_upgraded_without_losing_existing_data(tmp_db_path):
    """Reproduces the real-world scenario this bug report describes:
    a database that was migrated once, then fell behind head (here,
    deliberately stopped one migration short of head, matching the
    actual stale `database/veyra.db` this task found in the repository)."""
    settings = _settings_for(tmp_db_path)
    sync_url = _sync_db_url(settings)
    cfg = _build_alembic_config(sync_url)

    # Land one migration short of head — the exact revision the real
    # database/veyra.db was stuck at.
    command.upgrade(cfg, "c1a2f3b4d5e6")
    assert current_revision(settings) == "c1a2f3b4d5e6"

    con = sqlite3.connect(tmp_db_path)
    try:
        tables_before = {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "plugins" not in tables_before  # not yet migrated in

        con.execute(
            "INSERT INTO applications (id, identifier, name, aliases, executable_candidates, "
            "risk_level, enabled, verification_strategy, created_at, updated_at) VALUES "
            "('marker-id', 'marker_app', 'Marker App', '[]', '[]', 'SAFE', 1, "
            "'process_and_window_detection', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        con.commit()
    finally:
        con.close()

    revision = ensure_database_ready(settings)
    assert revision != "c1a2f3b4d5e6"

    con = sqlite3.connect(tmp_db_path)
    try:
        tables_after = {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "plugins" in tables_after  # the pending migration was applied

        marker = con.execute(
            "SELECT name FROM applications WHERE id = 'marker-id'"
        ).fetchone()
    finally:
        con.close()
    assert marker == ("Marker App",)  # pre-existing data survived the upgrade


def test_ensure_database_ready_raises_a_categorized_error_on_failure(tmp_db_path, monkeypatch):
    settings = _settings_for(tmp_db_path)

    def _broken_upgrade(*_args, **_kwargs):
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr("app.db.migrate.command.upgrade", _broken_upgrade)

    with pytest.raises(DatabaseInitializationError) as exc_info:
        ensure_database_ready(settings)
    assert "simulated migration failure" in exc_info.value.reason
    assert exc_info.value.resolution  # a real, non-empty actionable hint


def test_parent_directory_is_created_for_a_database_in_a_new_directory(tmp_path):
    nested = tmp_path / "does" / "not" / "exist" / "veyra.db"
    settings = _settings_for(nested)
    assert not nested.parent.exists()
    ensure_database_ready(settings)
    assert nested.exists()


def test_non_sqlite_url_is_a_no_op_for_file_precreation():
    from app.db.migrate import _sqlite_file_path

    assert _sqlite_file_path("postgresql://user:pass@host/db") is None
