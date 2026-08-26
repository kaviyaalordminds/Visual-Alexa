"""Configuration management. CLAUDE.md: 'The Local API binds to loopback
(127.0.0.1) only.' See docs/security/01-SECURITY-ARCHITECTURE.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VEYRA_", extra="ignore")

    app_name: str = "VEYRA Local API"
    environment: str = "development"

    # Never bind to a non-loopback interface by default — see
    # docs/security/03-THREAT-MODEL.md §5 (known limitation: no auth token
    # yet, so non-loopback exposure is not safe until that is addressed).
    host: str = "127.0.0.1"
    port: int = 8756

    database_url: str = "sqlite+aiosqlite:///./veyra.db"

    # Dev-only local secret encryption fallback — see
    # docs/security/05-DATA-PROTECTION.md §1. Production Windows builds use
    # DPAPI instead; this key must never be committed with a real value.
    secret_key: str = "dev-only-insecure-secret-change-me"

    log_level: str = "INFO"

    cors_origins: list[str] = ["tauri://localhost", "http://localhost:1420"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
