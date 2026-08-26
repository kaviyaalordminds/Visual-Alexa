"""End-to-end voice HTTP API tests — /voice/sessions... through the real
VoiceConversationManager/AgentOrchestrator chain. docs/phase-5/
PHASE-5-TEST-RESULTS.md.
"""

from __future__ import annotations

import os


async def test_start_submit_finish_end_round_trip(client, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")

    start = await client.post("/voice/sessions", json={})
    assert start.status_code == 201
    session = start.json()
    assert session["status"] == "LISTENING"
    assert session["conversation_id"] is not None

    turn = await client.post(
        f"/voice/sessions/{session['id']}/utterances", json={"text": "search for invoice"}
    )
    assert turn.status_code == 200
    body = turn.json()
    assert body["response"]["should_speak"] is True
    assert body["session"]["status"] == "RESPONDING"

    finished = await client.post(f"/voice/sessions/{session['id']}/finish_response")
    assert finished.status_code == 200
    assert finished.json()["status"] == "IDLE"

    messages = await client.get(f"/conversations/{session['conversation_id']}/messages")
    assert len(messages.json()) == 2  # user utterance + assistant response

    ended = await client.post(f"/voice/sessions/{session['id']}/end")
    assert ended.status_code == 204

    missing = await client.get(f"/voice/sessions/{session['id']}")
    assert missing.status_code == 404


async def test_unknown_session_returns_404(client):
    resp = await client.post(
        "/voice/sessions/does-not-exist/utterances", json={"text": "hello"}
    )
    assert resp.status_code == 404


async def test_barge_in_via_api(client, fs_sandbox):
    with open(os.path.join(fs_sandbox, "invoice.txt"), "w") as f:
        f.write("x")
    start = await client.post("/voice/sessions", json={})
    session_id = start.json()["id"]
    await client.post(
        f"/voice/sessions/{session_id}/utterances", json={"text": "search for invoice"}
    )

    interrupted = await client.post(
        f"/voice/sessions/{session_id}/utterances", json={"text": "Stop."}
    )
    body = interrupted.json()
    assert body["stop_speaking"] is True
    assert body["session"]["status"] == "LISTENING"
