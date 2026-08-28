# Phase 10 — Dependency & Build System Audit

## Version inventory (every manifest in the monorepo)

| File | Package/crate | Version |
|---|---|---|
| `package.json` (root) | `veyra` | `0.1.0` |
| `apps/desktop/package.json` | `veyra-desktop` | `0.1.0` |
| `apps/desktop/src-tauri/Cargo.toml` | `veyra-desktop` | `0.1.0` |
| `apps/desktop/src-tauri/tauri.conf.json` | `VEYRA` (productName) | `0.1.0` |
| `packages/contracts/typescript/package.json` | `@veyra/contracts` | `0.1.0` |
| `packages/contracts/python/pyproject.toml` | `veyra-contracts` | `0.1.0` |
| `services/computer-control/pyproject.toml` | `veyra-computer-control` | `0.1.0` |
| `services/local-api/pyproject.toml` | `veyra-local-api` | `0.1.0` |
| `services/vision/pyproject.toml` | `veyra-vision` | `0.1.0` |
| `services/voice/pyproject.toml` | `veyra-voice` | `0.1.0` |

**Every manifest matches `0.1.0`. No inconsistency, no missing version
field, no `requirements*.txt` files anywhere.** Version hygiene across the
monorepo is clean today — the one drift risk is that
`services/local-api/app/main.py` also hardcodes a *second*, independent
`version="0.1.0"` literal on the FastAPI app object (surfaces only in
`/openapi.json`, never read from `pyproject.toml`) — a duplicate source of
truth that could silently drift on a future version bump if only one of
the two is updated.

## Does the backend report its own version anywhere reachable?

No dedicated version endpoint. `Settings` has no `version` field; `/health`
and `/system` response models don't include one either. The only place a
version string appears at runtime is `GET /openapi.json`'s
`info.version` — undiscoverable unless you already know to look there.

## CI pipeline

**None exists.** No `.github/` directory, no `.gitlab-ci.yml`, no
`azure-pipelines.yml`, no CI config of any kind anywhere in the repo.
`scripts/check-python.sh`'s own header comment ("mirrors what CI should
run") implicitly acknowledges this gap.

## Build/release scripts

`scripts/` has exactly three files: `check-python.sh` (ruff + mypy ×5
packages + pytest), `dev-backend.bat` (venv setup + migrate + uvicorn),
`start-veyra.bat` (launches both dev servers + health-polls). Root
`package.json` only has thin workspace-delegate scripts
(`dev:desktop`/`build:desktop`/`lint:desktop`/`test:desktop`) — none of
them touch Python at all. **There is no single command that runs
everything** — Python and frontend checks are always two separate
invocations.

Python packaging: all five `pyproject.toml` files use plain
`setuptools.build_meta`, none has a `[project.scripts]` entry point.
PyInstaller/Nuitka/cx_Freeze appear nowhere in project config (only as
transitive artifacts inside `.venv`, e.g. Playwright's own bundled
PyInstaller hook — not something this project uses).

**There is currently no documented or scripted way to produce a single
distributable Windows artifact that bundles the Python backend.**
`cargo tauri build`/`npm run tauri build` would produce a Tauri/React
shell only (per `ARCHITECTURE-AUDIT.md` §1's sidecar-mechanism finding) —
nothing packages `services/local-api` into that artifact today.

## Test command inventory (for the runbook)

- Python: `bash scripts/check-python.sh` — ruff, then mypy × 5 packages,
  then `python3 -m pytest -q` from repo root.
- Frontend (`apps/desktop`): `npx vitest run`, `npx eslint .`, `npx tsc -b`.
- No root-level "run everything" command exists.

## `.gitignore` / secret hygiene

`.gitignore` covers `*.db`/`*.db-journal`, `.env`/`.env.local` (explicit
"Env / secrets" section), Python/Node/Rust build artifacts, `*.log`. No
broader credential-glob (`*.pem`, `*credentials*`, `*.enc.json`) — the
credentials store file isn't gitignored by name, though it lands outside
the repo root in normal use today. `git ls-files | grep -E '\.env$'`
returns no matches — **no committed `.env` file exists anywhere in the
repository.**
