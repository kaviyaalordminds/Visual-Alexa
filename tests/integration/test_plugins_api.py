"""HTTP-level plugin lifecycle. docs/phase-7/PLUGIN-ARCHITECTURE.md."""

from __future__ import annotations

_MANIFEST = {
    "id": "http-mock-plugin",
    "name": "HTTP Mock Plugin",
    "version": "1.0.0",
    "description": "A mock plugin installed via the HTTP API.",
    "author": "test",
    "permissions": ["filesystem.read", "network.access"],
    "tools": [],
    "dependencies": [],
    "entrypoint": "mock_plugin:main",
    "platforms": ["linux"],
}


async def test_install_via_http_never_executes_any_code(client):
    resp = await client.post("/plugins/install", json={"manifest": _MANIFEST})
    assert resp.status_code == 201
    body = resp.json()
    assert body["state"] == "UNTRUSTED"
    assert {p["permission"] for p in body["permissions"]} == {
        "filesystem.read",
        "network.access",
    }
    assert all(not p["granted"] for p in body["permissions"])


async def test_cannot_grant_an_unrequested_permission_via_http(client):
    install = await client.post("/plugins/install", json={"manifest": _MANIFEST})
    plugin_id = install.json()["id"]
    resp = await client.post(
        f"/plugins/{plugin_id}/permissions/grant", json={"permission": "filesystem.write"}
    )
    assert resp.status_code == 400


async def test_grant_then_trust_then_enable_via_http(client):
    install = await client.post("/plugins/install", json={"manifest": _MANIFEST})
    plugin_id = install.json()["id"]

    grant = await client.post(
        f"/plugins/{plugin_id}/permissions/grant", json={"permission": "filesystem.read"}
    )
    assert grant.status_code == 200
    granted = {p["permission"] for p in grant.json()["permissions"] if p["granted"]}
    assert granted == {"filesystem.read"}

    trust = await client.post(f"/plugins/{plugin_id}/trust")
    assert trust.status_code == 200
    assert trust.json()["state"] == "TRUSTED"

    enable = await client.post(f"/plugins/{plugin_id}/enable")
    assert enable.status_code == 200
    assert enable.json()["state"] == "ENABLED"


async def test_enable_before_trust_is_409(client):
    install = await client.post("/plugins/install", json={"manifest": _MANIFEST})
    plugin_id = install.json()["id"]
    resp = await client.post(f"/plugins/{plugin_id}/enable")
    assert resp.status_code == 409


async def test_remove_deletes_the_plugin(client):
    install = await client.post("/plugins/install", json={"manifest": _MANIFEST})
    plugin_id = install.json()["id"]
    resp = await client.delete(f"/plugins/{plugin_id}")
    assert resp.status_code == 204
    listed = (await client.get("/plugins")).json()
    assert plugin_id not in [p["id"] for p in listed]


async def test_unknown_plugin_operations_are_404(client):
    for method, path in [
        ("POST", "/plugins/does-not-exist/trust"),
        ("POST", "/plugins/does-not-exist/enable"),
        ("POST", "/plugins/does-not-exist/disable"),
        ("DELETE", "/plugins/does-not-exist"),
    ]:
        resp = await client.request(method, path)
        assert resp.status_code == 404, f"{method} {path}"
