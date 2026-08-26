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

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use the app's own settings for the DB URL, falling back to alembic.ini's
# default (sqlite+aiosqlite) only when app settings resolve to a different
# but still SQLite value; env vars (VEYRA_DATABASE_URL) always win.
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
