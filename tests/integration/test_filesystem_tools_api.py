"""Reproduces the Phase 2 brief's functional test scenarios §32 TEST 4-8
through the real HTTP API, against a real filesystem sandbox.
"""


async def _grant(client, tool_id, risk="MODERATE"):
    resp = await client.post(
        "/permissions", json={"tool_id": tool_id, "risk_level": risk, "scope": "ALLOW_SESSION"}
    )
    assert resp.status_code == 201


async def test_full_create_rename_search_flow(client, fs_sandbox):
    await _grant(client, "filesystem.create_folder")
    await _grant(client, "filesystem.create_file")
    await _grant(client, "filesystem.rename")

    # TEST 4: create Projects folder
    resp = await client.post(
        "/tools/filesystem.create_folder/invoke",
        json={"arguments": {"parent": fs_sandbox, "name": "Projects"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert body["output"]["status"] == "VERIFIED"
    projects_dir = body["output"]["data"]["metadata"]["path"]

    # TEST 5: create test.txt
    resp = await client.post(
        "/tools/filesystem.create_file/invoke",
        json={"arguments": {"parent": projects_dir, "name": "test.txt", "content": "hello veyra"}},
    )
    assert resp.status_code == 200
    assert resp.json()["output"]["status"] == "VERIFIED"
    test_txt_path = resp.json()["output"]["data"]["metadata"]["path"]

    # TEST 6: rename to veyra-test.txt
    resp = await client.post(
        "/tools/filesystem.rename/invoke",
        json={"arguments": {"path": test_txt_path, "new_name": "veyra-test.txt"}},
    )
    assert resp.status_code == 200
    renamed_path = resp.json()["output"]["data"]["metadata"]["path"]
    assert renamed_path.endswith("veyra-test.txt")

    # TEST 7: search for it
    resp = await client.post(
        "/tools/filesystem.search/invoke",
        json={"arguments": {"directory": projects_dir, "filename_contains": "veyra"}},
    )
    assert resp.status_code == 200
    matches = resp.json()["output"]["data"]["matches"]
    assert len(matches) == 1
    assert matches[0]["path"] == renamed_path


async def test_create_folder_without_grant_is_denied(client, fs_sandbox):
    resp = await client.post(
        "/tools/filesystem.create_folder/invoke",
        json={"arguments": {"parent": fs_sandbox, "name": "ShouldNotExist"}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PERMISSION_DENIED"


async def test_search_is_a_safe_tool_requiring_no_grant(client, fs_sandbox):
    resp = await client.post(
        "/tools/filesystem.search/invoke",
        json={"arguments": {"directory": fs_sandbox}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
