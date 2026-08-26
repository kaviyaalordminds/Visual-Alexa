# 05 — Data Protection

## 1. Secrets storage

- No secret (API key, OAuth token, device credential) is ever stored in
  plaintext in the SQLite database or in source control.
- **Decision**: on Windows, secrets are stored via **DPAPI**
  (`CryptProtectData`/`CryptUnprotectData`) through the Windows Credential
  Manager, evaluated as the correct choice because it is a first-party,
  per-user-encrypted OS mechanism requiring no additional key-management
  infrastructure, and is directly accessible from the Rust desktop shell via
  the `windows-rs` crate in future phases.
- **Decision**: on non-Windows dev/CI environments (this repository's build
  environment included), secrets use a local encrypted-at-rest fallback
  (`services/local-api` reads a `SECRET_KEY`-derived encryption for any
  local secret table) — documented as a dev-only fallback, not a production
  path; production Windows builds must use DPAPI.
- Database rows that reference a secret store only a `credentials_ref`
  (an opaque reference/key into the OS credential store), never the secret
  value itself. This is reflected in the `Connection`/`Integration` schema.

## 2. Data minimization

- Tool inputs/outputs are logged in the audit trail only to the extent
  needed for the audit log's purpose (what was requested, what tool, what
  outcome) — not full raw payload dumps of sensitive content by default.
- Memory records store only what a user explicitly stated or what a
  completed task actually produced — no speculative or inferred-without-basis
  data.

## 3. Microphone / screen / device defaults

Per product brief §29, restated normatively:

- **Microphone**: OFF unless enabled. No audio capture occurs without an
  explicit, visible user action; there is no hidden recording path.
- **Screen observation**: OFF unless enabled/required for an active,
  user-initiated task (see `docs/architecture/07-VISION.md` adaptive
  observation strategy). No hidden screen capture path.
- **External devices**: OFF until paired (see `04-DEVICE-TRUST.md`).
- **Remote control**: OFF by default; no remote-access surface exists in
  Phase 1 at all.

These defaults are represented as literal `SystemSetting` rows with
conservative defaults seeded by the initial migration, so "off by default"
is a database fact, not just documentation.

## 4. Encryption

- Database file: relies on OS-level filesystem permissions (user profile
  scoping) in Phase 1; full at-rest database encryption (e.g., SQLCipher) is
  documented as a future hardening step once real sensitive data is stored
  (Phase 1 stores no production user secrets).
- Local API traffic: loopback-only in Phase 1 (no network exposure to
  encrypt against); any future non-loopback exposure must add TLS before
  shipping, per the threat model's known limitation (`03-THREAT-MODEL.md` §5).

## 5. Phase 1 scope

Delivered: schema-level `credentials_ref` pattern, conservative default
`SystemSetting` rows, and documented DPAPI decision for the Windows
production path. Not delivered: a working DPAPI integration (requires a
Windows build target, see `docs/architecture/02-DESKTOP-ARCHITECTURE.md`
Known Phase 1 limitation) or SQLCipher-based at-rest encryption.
