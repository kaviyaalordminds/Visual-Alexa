"""Real, tesseract-backed OCR — genuinely executable in this environment
(unlike UI Automation). docs/phase-3/OCR.md, docs/phase-3/PHASE-3-TEST-RESULTS.md.
"""

from __future__ import annotations

import base64
import glob
import io
import os
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont
from vision.ocr.engine import OCREngine

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _render_text_image(text: str, font_path: str = _FONT_PATH, size: int = 28) -> str:
    img = Image.new("RGB", (max(300, 20 * len(text)), 80), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, size)
    draw.text((10, 20), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_extracts_real_english_text_with_confidence():
    engine = OCREngine()
    image_b64 = _render_text_image("Download")
    regions = engine.extract(image_b64)
    assert any(r.text == "Download" for r in regions)
    region = next(r for r in regions if r.text == "Download")
    assert 0.0 <= region.confidence <= 1.0
    assert region.confidence > 0.5
    assert region.bounds.width > 0 and region.bounds.height > 0


def test_blank_image_yields_no_text_regions():
    engine = OCREngine()
    img = Image.new("RGB", (200, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    regions = engine.extract(base64.b64encode(buf.getvalue()).decode())
    assert regions == []


def test_min_confidence_filters_low_confidence_regions():
    engine = OCREngine()
    image_b64 = _render_text_image("Download")
    regions = engine.extract(image_b64, min_confidence=0.99)
    assert all(r.confidence >= 0.99 for r in regions)


def test_unsupported_language_rejected():
    with pytest.raises(ValueError):
        OCREngine(languages=("fra",))


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract binary not installed")
def test_tamil_ocr_round_trips_with_noto_font():
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
        *glob.glob("/usr/share/fonts/**/NotoSansTamil*.ttf", recursive=True),
    ]
    font_path = next((c for c in candidates if os.path.exists(c)), None)
    if font_path is None:
        pytest.skip("No Tamil-capable font installed.")
    image_b64 = _render_text_image("பதிவிறக்கம்", font_path=font_path)
    engine = OCREngine(languages=("tam",))
    regions = engine.extract(image_b64, languages=("tam",))
    assert any("பதிவிறக்கம்" in r.text for r in regions)
