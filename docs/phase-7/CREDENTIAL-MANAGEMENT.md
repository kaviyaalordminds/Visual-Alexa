# Credential Management

## 1. What already existed, and what didn't

`credentials_ref` columns (opaque reference, never a raw secret) already
existed on `Integration`/`Device`/`Connection` since Phase 1 —
`docs/security/05-DATA-PROTECTION.md` §1 already specified the intended
design: DPAPI on Windows, "a local encrypted-at-rest fallback...
`SECRET_KEY`-derived" on non-Windows. `Settings.secret_key`
(`app/core/config.py`) was already added for exactly this, unused until
this phase. No `CredentialManager` class or module existed anywhere.

## 2. `CredentialStore` protocol, two implementations

```python
class CredentialStore(Protocol):
    def store(self, ref: str, secret: str) -> None: ...
    def retrieve(self, ref: str) -> str | None: ...
    def delete(self, ref: str) -> None: ...
```

- **`FileCredentialStore`** — the real, working implementation that ships
  and is tested here. A single JSON file of `{ref: fernet_ciphertext}`,
  encrypted with `cryptography`'s `Fernet` using a key derived via
  PBKDF2-HMAC-SHA256 (390,000 iterations) from `Settings.secret_key` and
  a fixed, documented salt — acceptable for a documented dev/non-Windows
  fallback, where secrecy comes from `secret_key`, not the salt. `chmod
  0600` on the file, best-effort.
- **`WindowsDPAPICredentialStore`** — a documented extension point,
  raises `NotImplementedError`. No Windows host exists in this
  environment to build or test `CryptProtectData`/`CryptUnprotectData`
  against — the same category as Phase 2's Windows-only backends: real
  code shape, not runtime-verifiable here. Swapping it in needs no
  change anywhere else, since every caller only ever depends on the
  `CredentialStore` protocol.

`cryptography` is a new, justified dependency: the stdlib has no
high-level authenticated encryption primitive, and hand-rolling one from
`hashlib`/`hmac` is exactly what CLAUDE.md's "never invent custom
cryptography... use established platform mechanisms" forbids.

## 3. `CredentialManager`

`store_credential(secret) -> ref` (a new opaque `cred_<uuid4>` string),
`retrieve_credential(ref) -> str | None`, `rotate_credential(ref,
new_secret)` (same ref, new secret — callers never need to update a
stored `credentials_ref` just because a token refreshed),
`delete_credential(ref)`, `validate_credential(ref) -> bool`. Every
method deals only in opaque refs — a caller (`IntegrationRegistry`,
`DevicePairingService`) never sees or logs a raw secret.

## 4. Verified

- Round-trip store/retrieve, delete, rotate, validate
  (`tests/unit/test_credential_manager.py`).
- The plaintext secret never appears in the on-disk file (asserted
  directly against the file's own bytes).
- A different `secret_key` cannot decrypt what a previous key encrypted.
- A corrupted or missing file is treated as "nothing stored," never a
  crash.
- End to end through the real HTTP API: a connected integration's secret
  never appears in any `AuditLog.request_payload_summary`/`target`, nor
  in the `GET /integrations` response body
  (`tests/security/test_phase7_platform_security.py`).

## 5. What's not delivered

A working DPAPI integration (needs a Windows build target — unchanged
limitation since Phase 1) and SQLCipher-based full-database encryption
(still documented as future hardening once real production secrets are
stored, per `docs/security/05-DATA-PROTECTION.md` §4).
