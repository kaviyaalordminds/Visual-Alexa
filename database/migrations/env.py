"""Alembic environment. Imports the Local API's SQLAlchemy models so
autogenerate has a real target_metadata — see CLAUDE.md 'All schema
changes go through Alembic migrations.'
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make services/local-api importable (models + settings) regardless of cwd.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
_LOCAL_API_DIR = os.path.join(_REPO_ROOT, "services", "local-api")
if _LOCAL_API_DIR not in sys.path:
    sys.path.insert(0, _LOCAL_API_DIR)

from app.core.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

# disable_existing_loggers=False — a real bug this migration path's own
# verification found: fileConfig()'s default (True) silently disables
# every logger that already existed (including the Local API's own
# app.core.logging.configure_logging() setup, when Alembic is invoked
# programmatically from app.db.migrate.ensure_database_ready() during
# FastAPI startup) rather than just adding alembic's console handler
# alongside them — every "[VEYRA] ..." startup log line after this point
# would otherwise silently vanish, not because startup failed but
# because its own logger got turned off out from under it.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Use the app's own settings for the DB URL — but only when the caller
# hasn't already set one explicitly. A real bug this module's own
# verification found: this used to *unconditionally* overwrite
# `sqlalchemy.url` with the process-global `get_settings()` singleton,
# silently discarding whatever URL a programmatic caller had already set
# on this exact `Config` object (app.db.migrate._build_alembic_config,
# used by both ensure_database_ready() at app startup and this project's
# own test suite to target an isolated, non-default database) — every
# such caller's migrations were actually running against the *default*
# database instead of the one it asked for. `config.attributes` is
# Alembic's documented mechanism for a programmatic caller to pass
# context into env.py; env.py only falls back to the global settings
# singleton for the plain-CLI case (`alembic upgrade head` with no
# programmatic wrapper), where nothing else could have supplied a URL.
if not config.attributes.get("veyra_explicit_url"):
    _settings = get_settings()
    _sync_url = _settings.database_url.replace("+aiosqlite", "")
    config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
