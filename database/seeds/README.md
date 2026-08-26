# Seeds

Non-migration seed data (e.g. demo/sample records for local development)
belongs here, kept separate from the schema-defining Alembic migrations in
`database/migrations`. Phase 1's only seed data — the conservative default
`SystemSetting` rows (docs/security/05-DATA-PROTECTION.md §3) — is itself
part of the schema's secure-by-default contract, so it lives in a migration
(`database/migrations/versions/..._seed_conservative_default_settings.py`)
rather than here. This directory is a placeholder for future
development-only sample data.
