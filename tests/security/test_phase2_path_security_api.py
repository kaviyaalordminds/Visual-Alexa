"""docs/phase-2 §32 TEST 11 — protected/traversal/UNC path access denied
through the real HTTP API, not just at the unit level.
"""

import pytest


async def _grant(client, tool_id, risk="MODERATE"):
    resp = await client.post(
        "/permissions", json={"tool_id": tool_id, "risk_level": risk, "scope": "ALLOW_SESSION"}
    )
    assert resp.status_code == 201


@pytest.mark.parametrize("protected_path", ["/etc/passwd", "/root/.ssh/id_rsa", "/bin/bash"])
async def test_get_metadata_on_protected_path_is_denied(client, protected_path):
    resp = await client.post(
        "/tools/filesystem.get_metadata/invoke", json={"arguments": {"path": protected_path}}
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PATH_PROTECTED"


async def test_create_folder_outside_allowed_roots_is_denied(client, fs_sandbox):
    await _grant(client, "filesystem.create_folder")
    resp = await client.post(
        "/tools/filesystem.create_folder/invoke",
        json={"arguments": {"parent": "/some/unrelated/path", "name": "evil"}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] in ("PATH_NOT_ALLOWED", "PATH_PROTECTED")


async def test_traversal_via_search_directory_is_denied(client, fs_sandbox):
    resp = await client.post(
        "/tools/filesystem.search/invoke",
        json={"arguments": {"directory": f"{fs_sandbox}/../../../etc"}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] in ("PATH_NOT_ALLOWED", "PATH_PROTECTED")


async def test_unc_path_is_denied(client):
    resp = await client.post(
        "/tools/filesystem.get_metadata/invoke",
        json={"arguments": {"path": r"\\attacker-server\share\payload.exe"}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PATH_NOT_ALLOWED"
