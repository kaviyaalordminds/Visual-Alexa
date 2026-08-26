#!/usr/bin/env bash
# Runs lint, type-check, and tests for the Python foundation
# (veyra-contracts + veyra-computer-control + local-api). Mirrors what CI
# should run. See CLAUDE.md testing rules.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== ruff =="
ruff check \
  "$REPO_ROOT/services/local-api" \
  "$REPO_ROOT/services/computer-control" \
  "$REPO_ROOT/services/vision" \
  "$REPO_ROOT/services/voice" \
  "$REPO_ROOT/packages/contracts/python" \
  "$REPO_ROOT/tests"

echo "== mypy: veyra-contracts =="
(cd "$REPO_ROOT/packages/contracts/python" && mypy veyra_contracts)

echo "== mypy: veyra-computer-control =="
(cd "$REPO_ROOT/services/computer-control" && mypy computer_control)

echo "== mypy: veyra-vision =="
(cd "$REPO_ROOT/services/vision" && mypy vision)

echo "== mypy: veyra-voice =="
(cd "$REPO_ROOT/services/voice" && mypy voice)

echo "== mypy: local-api =="
(cd "$REPO_ROOT/services/local-api" && mypy app)

echo "== pytest =="
(cd "$REPO_ROOT" && python3 -m pytest -q)
