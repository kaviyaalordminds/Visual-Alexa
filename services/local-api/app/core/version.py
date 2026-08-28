"""The one place the backend's own version string is defined. Part 53
(docs/phase-10 brief): "Version must be available in: desktop, frontend,
backend, diagnostics, installer. Do not allow services to report
conflicting versions."

This is a plain literal, not read from `pyproject.toml` at runtime,
because the same code path has to work identically in a source checkout
*and* inside the frozen sidecar (`scripts/build-backend-sidecar.py`),
where `pyproject.toml` isn't bundled and isn't guaranteed reachable —
the same class of problem `app/core/paths.py` solves for data files, but
a version string is simple enough not to need that machinery. Consistency
across every manifest in the repo (this file, `services/local-api/
pyproject.toml`, the root and desktop `package.json`, `Cargo.toml`,
`tauri.conf.json`) is enforced by `tests/unit/test_version_consistency.py`
— bump this alongside all of them, in the same change, or that test
fails.
"""

from __future__ import annotations

BACKEND_VERSION = "0.1.0"
