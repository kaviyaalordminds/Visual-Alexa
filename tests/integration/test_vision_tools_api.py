"""End-to-end tool-invocation tests for the Phase 3 visual-perception
tools, through the real Tool Registry -> Policy Engine -> Executor ->
Audit chain (the same HTTP surface docs/phase-2 tests already exercise).
docs/phase-3/PHASE-3-TEST-RESULTS.md.
"""

from __future__ import annotations

import base64
import io
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _render(text: str) -> str:
    img = Image.new("RGB", (300, 80), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), text, fill="black", font=ImageFont.truetype(_FONT_PATH, 28))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def test_ocr_extract_real_text(client):
    resp = await client.post(
        "/tools/ocr.extract/invoke",
        json={"arguments": {"image_base64": _render("Download"), "languages": ["eng"]}},
    )
    body = resp.json()
    assert body["status"] == "SUCCESS"
    regions = body["output"]["data"]["text_regions"]
    assert any(r["text"] == "Download" for r in regions)
    assert body["evidence_tier_used"] == "OCR"


async def test_ui_get_tree_platform_not_supported_on_this_host(client):
    resp = await client.post("/tools/ui.get_tree/invoke", json={"arguments": {}})
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PLATFORM_NOT_SUPPORTED"


async def test_scene_diff_pure_computation_no_gate_needed(client):
    before = {"root": {"name": "root", "role": "Window", "children": []}}
    after = {
        "root": {
            "name": "root",
            "role": "Window",
            "children": [{"name": "Saved!", "role": "Text"}],
        }
    }
    resp = await client.post(
        "/tools/scene.diff/invoke", json={"arguments": {"before": before, "after": after}}
    )
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert len(body["output"]["data"]["diff"]["added"]) == 1


async def test_target_ground_ambiguous_via_seeded_ui_tree(client, fake_computer_control):
    from computer_control.core.models import Rect, UIElementNode

    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    ui = fake_computer_control["ui_automation"]
    ui.seed_tree(
        UIElementNode(
            name="root",
            control_type="Window",
            children=[
                UIElementNode(
                    name="Download", control_type="Button",
                    bounds=Rect(left=0, top=0, width=80, height=20),
                ),
                UIElementNode(
                    name="Download PDF", control_type="Button",
                    bounds=Rect(left=100, top=0, width=80, height=20),
                ),
                UIElementNode(
                    name="Download Image", control_type="Button",
                    bounds=Rect(left=200, top=0, width=80, height=20),
                ),
            ],
        )
    )
    resp = await client.post(
        "/tools/target.ground/invoke", json={"arguments": {"target": {"text": "Download"}}}
    )
    body = resp.json()
    assert body["status"] == "SUCCESS"
    grounding = body["output"]["data"]["grounding"]
    assert grounding["status"] == "AMBIGUOUS_TARGET"
    assert len(grounding["candidates"]) == 3
    assert grounding["target"] is None


async def test_target_ground_single_match_is_grounded(client, fake_computer_control):
    from computer_control.core.models import Rect, UIElementNode

    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    ui = fake_computer_control["ui_automation"]
    ui.seed_tree(
        UIElementNode(
            name="root",
            control_type="Window",
            children=[
                UIElementNode(
                    name="Save", control_type="Button",
                    bounds=Rect(left=0, top=0, width=80, height=20),
                ),
            ],
        )
    )
    resp = await client.post(
        "/tools/target.ground/invoke", json={"arguments": {"target": {"text": "Save"}}}
    )
    body = resp.json()
    grounding = body["output"]["data"]["grounding"]
    assert grounding["status"] == "GROUNDED"
    assert grounding["target"]["name"] == "Save"


async def test_target_ground_denied_when_screen_observation_disabled(client):
    resp = await client.post(
        "/tools/target.ground/invoke", json={"arguments": {"target": {"text": "Save"}}}
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires a real (virtual) X display")
async def test_screen_observe_real_capture_and_privacy_default(client):
    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    resp = await client.post(
        "/tools/screen.observe/invoke",
        json={"arguments": {"include_ocr": True, "include_vision": False}},
    )
    body = resp.json()
    assert body["status"] == "SUCCESS"
    observation = body["output"]["data"]["observation"]
    assert observation["privacy_level"] in ("PUBLIC", "NORMAL", "PRIVATE", "SENSITIVE", "SECRET")
    assert "OCR" in observation["sources_used"]


async def test_screen_capture_region_moderate_risk_requires_grant(client):
    await client.patch("/settings/screen_observation.enabled", json={"value": True})
    resp = await client.post(
        "/tools/screen.capture_region/invoke",
        json={"arguments": {"bounds": {"left": 0, "top": 0, "width": 10, "height": 10}}},
    )
    body = resp.json()
    assert body["status"] == "FAILURE"
    assert body["error"]["code"] == "PERMISSION_DENIED"
