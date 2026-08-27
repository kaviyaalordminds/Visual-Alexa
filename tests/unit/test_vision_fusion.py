"""docs/phase-3/PERCEPTION-FUSION.md — merges same-element detections from
multiple sources into one GroundedElement with combined sources/confidence."""

from __future__ import annotations

from computer_control.core.models import Rect
from veyra_contracts import EvidenceTier
from vision.core.fusion import PerceptionFusion
from vision.core.models import SceneNode, TextRegion

_DOWNLOAD_BOUNDS = Rect(left=10, top=10, width=80, height=20)
_DOWNLOAD_TEXT_BOUNDS = Rect(left=12, top=11, width=76, height=18)


def test_overlapping_ui_node_and_ocr_text_merge_into_one_element():
    fusion = PerceptionFusion()
    node = SceneNode(name="Download", role="Button", bounds=_DOWNLOAD_BOUNDS)
    text = TextRegion(text="Download", confidence=0.9, bounds=_DOWNLOAD_TEXT_BOUNDS)
    fused = fusion.fuse(ui_nodes=[node], text_regions=[text])
    assert len(fused) == 1
    assert EvidenceTier.UI_AUTOMATION in fused[0].sources
    assert EvidenceTier.OCR in fused[0].sources


def test_non_overlapping_regions_stay_separate():
    fusion = PerceptionFusion()
    node = SceneNode(name="Download", role="Button", bounds=_DOWNLOAD_BOUNDS)
    far_bounds = Rect(left=500, top=500, width=80, height=20)
    text = TextRegion(text="Settings", confidence=0.9, bounds=far_bounds)
    fused = fusion.fuse(ui_nodes=[node], text_regions=[text])
    assert len(fused) == 2


def test_fused_confidence_at_least_as_high_as_best_single_source():
    fusion = PerceptionFusion()
    node = SceneNode(name="Download", role="Button", bounds=_DOWNLOAD_BOUNDS)
    text = TextRegion(text="Download", confidence=0.9, bounds=_DOWNLOAD_TEXT_BOUNDS)
    fused_multi = fusion.fuse(ui_nodes=[node], text_regions=[text])
    fused_single = fusion.fuse(ui_nodes=[node])
    assert fused_multi[0].confidence_score >= fused_single[0].confidence_score


def test_password_node_marks_privacy_secret():
    fusion = PerceptionFusion()
    node = SceneNode(
        name=None,
        role="Edit",
        automation_id="pwd",
        is_password=True,
        bounds=Rect(left=0, top=0, width=100, height=20),
    )
    fused = fusion.fuse(ui_nodes=[node])
    assert fused[0].privacy_level.value == "SECRET"
