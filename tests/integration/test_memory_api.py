"""docs/architecture/09-MEMORY.md §2 — inspectable, editable, deletable."""


async def test_memory_crud_round_trip(client):
    create_resp = await client.post(
        "/memory",
        json={
            "category": "WORKFLOW",
            "key": "office folder",
            "content": {"path": "D:\\Projects\\Office"},
            "source": "user_explicit",
        },
    )
    assert create_resp.status_code == 201
    record = create_resp.json()

    list_resp = await client.get("/memory")
    assert any(m["id"] == record["id"] for m in list_resp.json())

    filtered_resp = await client.get("/memory", params={"category": "WORKFLOW"})
    assert any(m["id"] == record["id"] for m in filtered_resp.json())

    update_resp = await client.patch(
        f"/memory/{record['id']}", json={"content": {"path": "D:\\Projects\\NewOffice"}}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["content"]["path"] == "D:\\Projects\\NewOffice"

    delete_resp = await client.delete(f"/memory/{record['id']}")
    assert delete_resp.status_code == 204

    final_list = await client.get("/memory")
    assert not any(m["id"] == record["id"] for m in final_list.json())


async def test_updating_unknown_memory_is_404(client):
    resp = await client.patch("/memory/does-not-exist", json={"content": {}})
    assert resp.status_code == 404
