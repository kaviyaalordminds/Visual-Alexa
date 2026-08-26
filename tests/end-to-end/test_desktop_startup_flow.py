"""End-to-end: the sequence of calls the Phase 1 desktop shell actually
makes on startup (docs/architecture/13-DATA-FLOW.md §3) plus one full
tool-execution round trip, exercised entirely through the public API — the
same surface the real Tauri shell talks to. This is the closest this
headless environment can get to a real Desktop <-> API <-> DB run; see the
final report for what still requires a Windows/GUI environment to verify.
"""


async def test_full_startup_and_status_flow(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    system = await client.get("/system")
    assert system.status_code == 200
    status = system.json()
    assert status["desktop"] == "CONNECTED"
    assert status["local_api"] == "CONNECTED"
    assert status["database"] == "CONNECTED"
    assert status["security"] == "ACTIVE"

    tools = await client.get("/tools")
    assert tools.status_code == 200
    assert len(tools.json()) >= 1

    settings = await client.get("/settings")
    assert settings.status_code == 200
    assert len(settings.json()) >= 1


async def test_full_task_and_tool_execution_round_trip(client):
    task_resp = await client.post(
        "/tasks",
        json={
            "description": "check system status",
            "budget": {"max_steps": 3, "timeout_seconds": 30, "max_recovery_attempts": 0},
        },
    )
    assert task_resp.status_code == 201
    task = task_resp.json()
    assert task["state"] == "RECEIVED"

    invoke_resp = await client.post("/tools/system.get_status/invoke", json={})
    assert invoke_resp.status_code == 200
    assert invoke_resp.json()["status"] == "SUCCESS"

    fetched = await client.get(f"/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == task["id"]
