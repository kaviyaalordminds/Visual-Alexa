"""docs/architecture/14-TASK-LIFECYCLE.md — TaskBudget is mandatory."""


async def test_create_task_requires_a_budget(client):
    resp = await client.post("/tasks", json={"description": "no budget here"})
    assert resp.status_code == 422


async def test_create_and_fetch_task(client):
    create_resp = await client.post(
        "/tasks",
        json={
            "description": "search for invoices",
            "budget": {"max_steps": 10, "timeout_seconds": 60, "max_recovery_attempts": 2},
        },
    )
    assert create_resp.status_code == 201
    task = create_resp.json()
    assert task["state"] == "RECEIVED"

    get_resp = await client.get(f"/tasks/{task['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task["id"]


async def test_budget_exceeding_the_bound_is_rejected(client):
    resp = await client.post(
        "/tasks",
        json={
            "description": "unbounded loop attempt",
            "budget": {"max_steps": 100000, "timeout_seconds": 60, "max_recovery_attempts": 1},
        },
    )
    assert resp.status_code == 422
