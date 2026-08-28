"""Configuration management. CLAUDE.md: 'The Local API binds to loopback
(127.0.0.1) only.' See docs/security/01-SECURITY-ARCHITECTURE.md.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The one canonical, cwd-independent location for VEYRA's SQLite database
# and Alembic's own migration target (database/migrations/env.py reads
# this same Settings.database_url — see that file's own comment). A bare
# relative default ("./veyra.db") silently resolves against whatever
# directory a process happens to be launched from: `alembic upgrade head`
# is conventionally run from `database/`, `uvicorn app.main:app` from
# `services/local-api/` — two different directories, so a relative
# default produces two different SQLite files, one of them never
# migrated. Anchoring to this file's own location instead of the process
# cwd is what makes "the app" and "Alembic" always agree, regardless of
# where either is invoked from.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DB_PATH = _REPO_ROOT / "database" / "veyra.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VEYRA_", extra="ignore")

    app_name: str = "VEYRA Local API"
    environment: str = "development"

    # Never bind to a non-loopback interface by default — see
    # docs/security/03-THREAT-MODEL.md §5 (known limitation: no auth token
    # yet, so non-loopback exposure is not safe until that is addressed).
    host: str = "127.0.0.1"
    port: int = 8756

    database_url: str = f"sqlite+aiosqlite:///{_DEFAULT_DB_PATH}"

    # Dev-only local secret encryption fallback — see
    # docs/security/05-DATA-PROTECTION.md §1. Production Windows builds use
    # DPAPI instead; this key must never be committed with a real value.
    secret_key: str = "dev-only-insecure-secret-change-me"

    # Phase 7 (docs/phase-7/CREDENTIAL-MANAGEMENT.md) — where
    # FileCredentialStore persists its encrypted blobs. Never plaintext;
    # see app/services/credential_manager.py.
    credentials_store_path: str = "./credentials.enc.json"

    log_level: str = "INFO"

    cors_origins: list[str] = ["tauri://localhost", "http://localhost:1420"]

    # Phase 2: docs/phase-2/FILESYSTEM-CONTROL.md §7.2. None = use
    # app.services.filesystem_config's platform-appropriate default
    # (Documents/Downloads/Desktop on Windows). Never defaults to
    # allow-all — see computer_control.filesystem.path_policy.PathPolicy.
    filesystem_allowed_roots: list[str] | None = None

    # Phase 8 (docs/phase-8/DOWNLOADS.md) — where PlaywrightBrowserAdapter
    # saves a browser-triggered download's bytes.
    browser_downloads_dir: str = "./browser-downloads"
    # Phase 8 (docs/phase-8/EXTENSION-BRIDGE.md) — brief §73 'validate
    # origin.' Empty by default: no extension origin is trusted until an
    # operator explicitly configures one, matching the platform's
    # default-deny posture everywhere else.
    browser_extension_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()
