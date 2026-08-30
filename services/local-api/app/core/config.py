"""Configuration management. CLAUDE.md: 'The Local API binds to loopback
(127.0.0.1) only.' See docs/security/01-SECURITY-ARCHITECTURE.md.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import resolve_app_data_dir

# The one canonical location for VEYRA's SQLite database and Alembic's own
# migration target (database/migrations/env.py reads this same
# Settings.database_url — see that file's own comment), and for every
# other piece of mutable data this app owns. Phase 10 P0-2 (docs/phase-10/
# ARCHITECTURE-AUDIT.md §5-6): this used to be anchored to this file's own
# location in the source tree (cwd-independent, but still inside
# whatever directory happened to contain the checkout) — wrong for an
# installed app (`C:\Program Files\VEYRA\` needs admin rights to write to
# and isn't multi-user-safe) and, per Part 35, not the right place for
# mutable data even in dev. `resolve_app_data_dir()` is the one place
# this decision is made; `VEYRA_APP_DATA_DIR` overrides it (used by the
# test suite for isolation — see tests/conftest.py).
_APP_DATA_DIR = resolve_app_data_dir()
_DEFAULT_DB_PATH = _APP_DATA_DIR / "database" / "veyra.db"
_DEFAULT_CREDENTIALS_STORE_PATH = _APP_DATA_DIR / "credentials.enc.json"
_DEFAULT_BROWSER_DOWNLOADS_DIR = _APP_DATA_DIR / "browser-downloads"


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
    credentials_store_path: str = str(_DEFAULT_CREDENTIALS_STORE_PATH)

    log_level: str = "INFO"

    cors_origins: list[str] = ["tauri://localhost", "http://localhost:1420"]

    # Phase 2: docs/phase-2/FILESYSTEM-CONTROL.md §7.2. None = use
    # app.services.filesystem_config's platform-appropriate default
    # (Documents/Downloads/Desktop on Windows). Never defaults to
    # allow-all — see computer_control.filesystem.path_policy.PathPolicy.
    filesystem_allowed_roots: list[str] | None = None

    # Phase 8 (docs/phase-8/DOWNLOADS.md) — where PlaywrightBrowserAdapter
    # saves a browser-triggered download's bytes.
    browser_downloads_dir: str = str(_DEFAULT_BROWSER_DOWNLOADS_DIR)
    # Phase 8 (docs/phase-8/EXTENSION-BRIDGE.md) — brief §73 'validate
    # origin.' Empty by default: no extension origin is trusted until an
    # operator explicitly configures one, matching the platform's
    # default-deny posture everywhere else.
    browser_extension_origins: list[str] = []

    # --- Subsystem activation: AI/Voice/Vision provider configuration ---
    # docs/subsystem-activation/. Empty string = "not configured", the
    # same convention every other optional subsystem already uses
    # (NotConfiguredLLMProvider/NotConfiguredVisionProvider/voice's
    # NotConfigured* providers). Never a hardcoded real value; set via
    # VEYRA_AI_* env vars in a local .env, never committed. The API key
    # is never returned by any endpoint or logged — only whether it is
    # present is ever reported (see app/services/subsystem_health.py).
    ai_provider: str = ""
    ai_model: str = ""
    ai_api_key: str = ""
    # An OpenAI-compatible chat-completions base URL (works for OpenAI
    # itself, many OpenAI-compatible cloud providers, and a local
    # Ollama/LM Studio-style server) — deliberately generic so VEYRA is
    # never hard-coded to one vendor, per CLAUDE.md's provider-abstraction
    # rule. No vendor SDK is imported for this; app/services/agent/
    # providers/cloud_llm_provider.py speaks plain HTTP via httpx.
    ai_base_url: str = ""

    # Declares which real provider family to use for each capability —
    # "whisper_cpp"/"piper"/"openwakeword" select the real classes in
    # services/voice/voice/providers/real.py (app/services/voice/
    # register.py does the actual wiring); any other value, or blank,
    # keeps that capability on the honest NotConfigured* fallback.
    stt_provider: str = ""
    tts_provider: str = ""
    wake_word_provider: str = ""

    # openWakeWord: one of its bundled pretrained phrases (e.g.
    # "hey_jarvis", "alexa", "hey_mycroft", "hey_rhasspy") — a custom
    # "Hey VEYRA" model needs training data and is not shipped here, see
    # docs/voice-hardware/SETUP.md.
    wake_word_model: str = "hey_jarvis"
    wake_word_threshold: float = 0.5

    # pywhispercpp: a known whisper.cpp shorthand name (auto-downloaded
    # on first use) or a direct path to an existing ggml model file.
    whisper_model: str = "base.en"
    whisper_models_dir: str = ""

    # Piper: a real voice .onnx file path the operator downloads once —
    # never a name pywhispercpp-style auto-resolves, since Piper voices
    # are per-language/per-speaker files with no single "default" to
    # fetch. Blank keeps TTS on NotConfiguredTTS regardless of
    # `tts_provider`.
    piper_voice_model_path: str = ""

    # Optional device selection for the real sounddevice-backed
    # AudioInput/AudioOutput — blank uses the OS default device.
    audio_input_device: str = ""
    audio_output_device: str = ""

    # Declares intent to use a real vision *model* provider (distinct
    # from OCR/screen-capture, which are already real and checked
    # independently — see vision's own NotConfiguredVisionProvider).
    vision_provider: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
