"""Applies pending Alembic migrations against VEYRA's own database before
anything else touches it. docs/architecture/01-SYSTEM-ARCHITECTURE.md;
CLAUDE.md: "All schema changes go through Alembic migrations — never
hand-edit the database file or apply ad hoc DDL."

Root cause this module fixes: nothing in the FastAPI startup path ever
applied or even verified migrations before `load_application_registry`
(and everything after it) started querying tables that may not exist yet
— "no such table: applications" on a brand-new database, or a stale
schema on an existing-but-outdated one. `ensure_database_ready()` is the
one place that changes: called once, first, from `app.main`'s lifespan.

Safe on every run:
- No database file yet -> Alembic creates it and runs every migration
  from the beginning (brief STEP 6 "first run").
- Database exists at an older revision -> Alembic applies only the
  pending migrations, in order, exactly like running `alembic upgrade
  head` by hand (brief STEP 6 "subsequent run"). Existing rows are
  never touched by a migration that doesn't itself change their table.
- Database already at head -> `alembic.command.upgrade(cfg, "head")` is
  a real no-op; nothing is re-applied.

Never drops or deletes anything — this module has no code path that can
destroy data, matching CLAUDE.md's testing/migration-safety rules.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import Settings
from app.core.logging import configure_logging
from app.core.paths import resolve_bundled_resource_dir

logger = logging.getLogger(__name__)

# Phase 10 P0-1 (docs/phase-10/ARCHITECTURE-AUDIT.md §5-6): alembic.ini
# and migrations/ are read-only, shipped resources, not user data — see
# resolve_bundled_resource_dir()'s own docstring for exactly why a frozen
# sidecar build resolves this differently (PyInstaller's extraction
# directory) than a source checkout (the repo root).
_BUNDLED_RESOURCE_DIR = resolve_bundled_resource_dir()
_ALEMBIC_INI = _BUNDLED_RESOURCE_DIR / "database" / "alembic.ini"
_MIGRATIONS_DIR = _BUNDLED_RESOURCE_DIR / "database" / "migrations"


class DatabaseInitializationError(RuntimeError):
    """Raised when the database cannot be brought to a ready (migrated)
    state. Carries a `resolution` hint distinct from the raw exception,
    so `app.main`'s lifespan can log something a developer can actually
    act on instead of only a SQLAlchemy/Alembic traceback."""

    def __init__(self, reason: str, resolution: str, *, cause: Exception | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.resolution = resolution
        self.__cause__ = cause


def _sync_db_url(settings: Settings) -> str:
    # Alembic's `command.upgrade` runs synchronously — it needs the plain
    # `sqlite:///` driver, not the app's own async `sqlite+aiosqlite:///`
    # one. Mirrors migrations/env.py's own identical conversion.
    return settings.database_url.replace("+aiosqlite", "")


def _sqlite_file_path(sync_url: str) -> Path | None:
    # A non-SQLite database_url (e.g. a future Postgres one) needs no
    # local file precreated.
    prefix = "sqlite:///"
    if not sync_url.startswith(prefix):
        return None
    return Path(sync_url[len(prefix) :])


def _build_alembic_config(sync_url: str) -> Config:
    if not _ALEMBIC_INI.exists():
        raise DatabaseInitializationError(
            reason=f"Alembic config not found at {_ALEMBIC_INI}.",
            resolution="Verify the repository layout — database/alembic.ini must exist.",
        )
    cfg = Config(str(_ALEMBIC_INI))
    # Belt-and-braces: explicit absolute paths, never left to cwd-relative
    # resolution (see alembic.ini's own comment on `%(here)s`).
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    # Tells migrations/env.py this URL was set deliberately by us and
    # must never be overwritten by its own get_settings() fallback — see
    # that file's own comment for the real bug this fixes.
    cfg.attributes["veyra_explicit_url"] = True
    return cfg


def current_revision(settings: Settings) -> str | None:
    """The database's current `alembic_version` row, or `None` for a
    database that doesn't exist yet / has never been stamped. Read-only —
    safe to call from a health-check endpoint."""
    sync_url = _sync_db_url(settings)
    file_path = _sqlite_file_path(sync_url)
    if file_path is not None and not file_path.exists():
        return None
    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            if "alembic_version" not in inspect(conn).get_table_names():
                return None
            row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
            return row[0] if row else None
    finally:
        engine.dispose()


def ensure_database_ready(settings: Settings) -> str:
    """Applies every pending migration, in order, up to `head`. Returns
    the resulting revision (for startup logging / a future health
    endpoint). Raises `DatabaseInitializationError` on failure — the
    caller (`app.main`'s lifespan) treats this as fatal: the Local API
    cannot serve any request that touches the database, so it should not
    pretend to have started successfully."""
    sync_url = _sync_db_url(settings)
    file_path = _sqlite_file_path(sync_url)
    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    before = current_revision(settings)
    logger.info(
        "[VEYRA] Database: checking migrations (current=%s)", before or "none (fresh database)"
    )

    cfg = _build_alembic_config(sync_url)
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        # Real bug this module's own verification found: Alembic's env.py
        # calls fileConfig() (to set up its own console log formatting),
        # which replaces the *root* logger's handlers/level wholesale —
        # every log call below this point would otherwise be silently
        # dropped (not because anything failed, but because the handler
        # that would have printed it is gone). Restore our own logging
        # setup immediately after Alembic is done touching it, success or
        # failure, before logging anything else.
        configure_logging(settings.log_level)
        raise DatabaseInitializationError(
            reason=f"Alembic migration failed: {exc}",
            resolution=(
                "Inspect the database file directly (it is never deleted by this step) and the "
                "migration that failed; fix the migration or the schema drift it found, then "
                "restart. Never hand-edit the schema to work around this."
            ),
            cause=exc,
        ) from exc
    configure_logging(settings.log_level)

    after = current_revision(settings)
    if after is None:
        raise DatabaseInitializationError(
            reason="Migrations reported success but no alembic_version row exists afterward.",
            resolution="This should not happen — inspect database/migrations/versions/ for a "
            "migration that never calls op.execute for the version stamp (Alembic normally "
            "handles this automatically).",
        )
    logger.info("[VEYRA] Database: schema READY (revision=%s)", after)
    return after
