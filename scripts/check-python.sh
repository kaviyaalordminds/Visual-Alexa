#!/usr/bin/env bash
# Runs lint, type-check, and tests for the Python foundation (veyra-contracts
# + local-api). Mirrors what CI should run. See CLAUDE.md testing rules.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== ruff =="
ruff check "$REPO_ROOT/services/local-api" "$REPO_ROOT/packages/contracts/python" "$REPO_ROOT/tests"

echo "== mypy: veyra-contracts =="
(cd "$REPO_ROOT/packages/contracts/python" && mypy veyra_contracts)

echo "== mypy: local-api =="
(cd "$REPO_ROOT/services/local-api" && mypy app)

echo "== pytest =="
(cd "$REPO_ROOT" && python3 -m pytest -q)
