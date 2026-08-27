"""CredentialManager — secure storage for integration/device secrets.
docs/security/05-DATA-PROTECTION.md §1, docs/phase-7/CREDENTIAL-MANAGEMENT.md.

Never stores a raw secret anywhere a `credentials_ref` column can reach —
`Integration.credentials_ref`/`Device.credentials_ref`/`Connection.
credentials_ref` only ever hold the opaque `ref` this module returns, the
secret itself lives only inside a `CredentialStore`.

Two backends, matching the already-documented design decision exactly:
`FileCredentialStore` is the real, working non-Windows fallback (this
environment has no Windows host, so it's also what ships and is tested
here); `WindowsDPAPICredentialStore` is a documented extension point that
raises `NotImplementedError` — the same category as Phase 2's
Windows-only backends, real code shape, not runtime-testable here.
"""

from __future__ import annotations

import base64
import json
import os
import platform
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import get_settings

# A fixed, documented salt is acceptable here: this is a *dev/non-Windows
# fallback* (docs/security/05-DATA-PROTECTION.md §1), not the production
# path (DPAPI, which needs no salt at all — it's OS-managed). The
# property that matters is determinism across restarts, so a credential
# stored last run can still be decrypted this run; secrecy comes from
# `Settings.secret_key`, not from the salt.
_KDF_SALT = b"veyra-phase-7-credential-store-v1"


class CredentialStore(Protocol):
    def store(self, ref: str, secret: str) -> None: ...
    def retrieve(self, ref: str) -> str | None: ...
    def delete(self, ref: str) -> None: ...


def _derive_key(secret_key: str) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_KDF_SALT, iterations=390_000)
    return base64.urlsafe_b64encode(kdf.derive(secret_key.encode("utf-8")))


class FileCredentialStore:
    """The real non-Windows fallback: a single JSON file of
    `{ref: fernet_ciphertext}`, encrypted with a key derived from
    `Settings.secret_key`. Simple read-modify-write — this is a local,
    single-process, low-volume store (integration/device credentials,
    not a general secrets database), so no separate locking layer is
    warranted."""

    def __init__(self, *, secret_key: str, path: str | Path) -> None:
        self._fernet = Fernet(_derive_key(secret_key))
        self._path = Path(path)

    def _read_all(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_all(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data))
        # Best-effort — matches docs/security/05-DATA-PROTECTION.md §4's
        # "relies on OS-level filesystem permissions" for the dev
        # fallback; not fatal if the platform doesn't support chmod.
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    def store(self, ref: str, secret: str) -> None:
        data = self._read_all()
        data[ref] = self._fernet.encrypt(secret.encode("utf-8")).decode("ascii")
        self._write_all(data)

    def retrieve(self, ref: str) -> str | None:
        ciphertext = self._read_all().get(ref)
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken:
            # Wrong/rotated secret_key, or corrupted file — never raise
            # into a caller expecting "credential missing or unreadable",
            # same as a genuinely-absent ref.
            return None

    def delete(self, ref: str) -> None:
        data = self._read_all()
        if ref in data:
            del data[ref]
            self._write_all(data)


class WindowsDPAPICredentialStore:
    """Documented extension point, not implemented — see
    docs/security/05-DATA-PROTECTION.md §1's DPAPI decision and §5's own
    'Not delivered' note. No Windows host exists in this environment to
    build or test `CryptProtectData`/`CryptUnprotectData` against (the
    same category as Phase 2's Windows-only computer-control backends);
    a future Windows build swaps this in behind the same `CredentialStore`
    Protocol, with no change needed anywhere else in this module."""

    def __init__(self) -> None:
        if platform.system() != "Windows":
            raise NotImplementedError(
                "WindowsDPAPICredentialStore requires a Windows host "
                "(CryptProtectData/CryptUnprotectData); none exists here. "
                "Use FileCredentialStore instead."
            )
        raise NotImplementedError(  # pragma: no cover - no Windows CI host
            "DPAPI integration is designed, not yet implemented."
        )

    def store(self, ref: str, secret: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def retrieve(self, ref: str) -> str | None:  # pragma: no cover
        raise NotImplementedError

    def delete(self, ref: str) -> None:  # pragma: no cover
        raise NotImplementedError


class CredentialManager:
    """Responsibilities per brief §20: store, retrieve, delete, rotate,
    validate. Every method deals only in opaque `ref` strings — a caller
    (IntegrationRegistry, DevicePairingService) never sees or logs a raw
    secret."""

    def __init__(self, store: CredentialStore) -> None:
        self._store = store

    def store_credential(self, secret: str) -> str:
        ref = f"cred_{uuid4().hex}"
        self._store.store(ref, secret)
        return ref

    def retrieve_credential(self, ref: str) -> str | None:
        return self._store.retrieve(ref)

    def rotate_credential(self, ref: str, new_secret: str) -> None:
        """Same `ref`, new secret — callers (Integration rows) never need
        to update a stored `credentials_ref` just because the underlying
        token was refreshed."""
        self._store.store(ref, new_secret)

    def delete_credential(self, ref: str) -> None:
        self._store.delete(ref)

    def validate_credential(self, ref: str) -> bool:
        return self._store.retrieve(ref) is not None


def _build_default_store() -> CredentialStore:
    settings = get_settings()
    return FileCredentialStore(secret_key=settings.secret_key, path=settings.credentials_store_path)


# Module-level singleton — mirrors tool_registry/policy_engine/event_bus:
# this process is the only one with database (and now credential-store)
# access, so one in-process instance is sufficient.
credential_manager = CredentialManager(_build_default_store())
