"""Part 53: "Version must be available in: desktop, frontend, backend,
diagnostics, installer. Do not allow services to report conflicting
versions." This is the enforcement — every manifest in the repo must
agree with app.core.version.BACKEND_VERSION, checked directly against
each real file, not against a second copy of the expected value.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from app.core.version import BACKEND_VERSION

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_local_api_pyproject_matches_backend_version():
    data = tomllib.loads(
        (_REPO_ROOT / "services" / "local-api" / "pyproject.toml").read_text()
    )
    assert data["project"]["version"] == BACKEND_VERSION


def test_root_package_json_matches_backend_version():
    data = json.loads((_REPO_ROOT / "package.json").read_text())
    assert data["version"] == BACKEND_VERSION


def test_desktop_package_json_matches_backend_version():
    data = json.loads((_REPO_ROOT / "apps" / "desktop" / "package.json").read_text())
    assert data["version"] == BACKEND_VERSION


def test_desktop_cargo_toml_matches_backend_version():
    data = tomllib.loads(
        (_REPO_ROOT / "apps" / "desktop" / "src-tauri" / "Cargo.toml").read_text()
    )
    assert data["package"]["version"] == BACKEND_VERSION


def test_tauri_conf_json_matches_backend_version():
    data = json.loads(
        (_REPO_ROOT / "apps" / "desktop" / "src-tauri" / "tauri.conf.json").read_text()
    )
    assert data["version"] == BACKEND_VERSION


def test_fastapi_app_object_reports_backend_version():
    from app.main import app

    assert app.version == BACKEND_VERSION


def test_backend_version_is_a_real_semver_string():
    assert re.match(r"^\d+\.\d+\.\d+$", BACKEND_VERSION)
