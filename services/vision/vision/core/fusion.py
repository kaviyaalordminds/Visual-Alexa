"""Perception fusion: merges same-element detections from multiple
sources (UIA scene nodes, OCR text regions, vision-model regions) into
`GroundedElement`s with a combined `sources` list and combined confidence.
docs/phase-3/PERCEPTION-FUSION.md.

Pure Python, no OS dependency — genuinely tested here.
"""

from __future__ import annotations

from computer_control.core.models import Rect
from veyra_contracts import ContentSource, EvidenceTier

from vision.core.confidence import base_score_for_tier, combine_scores, score_to_band
from vision.core.models import GroundedElement, SceneNode, TextRegion, VisualRegion
from vision.core.privacy import PrivacyLevel, SecretDetector


def _overlap_ratio(a: Rect, b: Rect) -> float:
    """Intersection-over-union of two rectangles, 0 when disjoint."""
    left = max(a.left, b.left)
    top = max(a.top, b.top)
    right = min(a.left + a.width, b.left + b.width)
    bottom = min(a.top + a.height, b.top + b.height)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = a.width * a.height + b.width * b.height - intersection
    if union <= 0:
        return 0.0
    return intersection / union


_SAME_ELEMENT_OVERLAP_THRESHOLD = 0.5


class PerceptionFusion:
    """docs/phase-3 §19 — merges detections whose bounding boxes overlap
    above `overlap_threshold` into one `GroundedElement`, carrying forward
    every contributing source and a combined (not merely max) confidence
    score."""

    def __init__(
        self,
        *,
        overlap_threshold: float = _SAME_ELEMENT_OVERLAP_THRESHOLD,
        secret_detector: SecretDetector | None = None,
    ) -> None:
        self._overlap_threshold = overlap_threshold
        self._detector = secret_detector or SecretDetector()

    def fuse(
        self,
        *,
        ui_nodes: list[SceneNode] | None = None,
        text_regions: list[TextRegion] | None = None,
        visual_regions: list[VisualRegion] | None = None,
    ) -> list[GroundedElement]:
        candidates: list[GroundedElement] = []
        for node in ui_nodes or []:
            if node.bounds is None:
                continue
            candidates.append(
                GroundedElement(
                    name=node.name,
                    role=node.role,
                    text=node.name,
                    bounds=node.bounds,
                    visible=node.visible,
                    enabled=node.enabled,
                    is_password=node.is_password,
                    privacy_level=(
                        PrivacyLevel.SECRET if node.is_password else PrivacyLevel.NORMAL
                    ),
                    sources=[EvidenceTier.UI_AUTOMATION],
                    confidence_score=base_score_for_tier(EvidenceTier.UI_AUTOMATION),
                    source_content=ContentSource.UI_OBSERVATION,
                )
            )
        for region in text_regions or []:
            candidates.append(
                GroundedElement(
                    name=region.text,
                    role="text",
                    text=region.text,
                    bounds=region.bounds,
                    privacy_level=self._detector.classify_text(region.text),
                    sources=[EvidenceTier.OCR],
                    confidence_score=region.confidence * base_score_for_tier(EvidenceTier.OCR),
                    source_content=ContentSource.UI_OBSERVATION,
                )
            )
        for visual in visual_regions or []:
            candidates.append(
                GroundedElement(
                    name=visual.label,
                    role=visual.region_type,
                    bounds=visual.bounds,
                    sources=[visual.source],
                    confidence_score=visual.confidence * base_score_for_tier(visual.source),
                    source_content=ContentSource.UI_OBSERVATION,
                )
            )
        return self._merge(candidates)

    def _merge(self, candidates: list[GroundedElement]) -> list[GroundedElement]:
        merged: list[GroundedElement] = []
        used = [False] * len(candidates)
        for i, candidate in enumerate(candidates):
            if used[i]:
                continue
            used[i] = True
            group = [candidate]
            if candidate.bounds is not None:
                for j in range(i + 1, len(candidates)):
                    if used[j] or candidates[j].bounds is None:
                        continue
                    if _overlap_ratio(candidate.bounds, candidates[j].bounds) >= (
                        self._overlap_threshold
                    ):
                        used[j] = True
                        group.append(candidates[j])
            merged.append(self._combine(group))
        return merged

    def _combine(self, group: list[GroundedElement]) -> GroundedElement:
        primary = max(group, key=lambda e: e.confidence_score)
        sources: list[EvidenceTier] = []
        for element in group:
            for source in element.sources:
                if source not in sources:
                    sources.append(source)
        combined_score = combine_scores([e.confidence_score for e in group])
        privacy = max(
            (e.privacy_level for e in group),
            key=lambda level: list(PrivacyLevel).index(level),
        )
        return primary.model_copy(
            update={
                "sources": sources,
                "confidence_score": combined_score,
                "confidence_band": score_to_band(combined_score),
                "privacy_level": privacy,
            }
        )
