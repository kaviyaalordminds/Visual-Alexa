"""Real, tesseract-based OCR engine. docs/phase-3/OCR.md.

Cross-platform (unlike UI Automation) — genuinely verified in this
container: `pytesseract.image_to_data` against real rendered English and
Tamil text round-trips correctly (see docs/phase-3/PHASE-3-TEST-RESULTS.md
for the exact captured output).

docs/phase-3 §9: 'do not assume OCR is always correct' — every
`TextRegion` this engine returns carries tesseract's own per-word
confidence; nothing here upgrades a low-confidence read to a
higher-confidence one, and callers (fusion/grounding) are expected to
weight OCR results accordingly (docs/architecture/05-COMPUTER-CONTROL.md
§1: OCR is tier 6, below every structured source).
"""

from __future__ import annotations

import base64
import io

from computer_control.core.models import Rect
from PIL import Image
from veyra_contracts import ErrorCategory

from vision.core.models import TextRegion

# docs/phase-3 §9 — 'Support: English, Tamil' with an explicit note that
# more languages can be added later. pytesseract/tesseract language codes,
# not display names.
SUPPORTED_LANGUAGES = ("eng", "tam")
DEFAULT_LANGUAGES = ("eng",)


class OCRUnavailableError(RuntimeError):
    """Raised when the system `tesseract` binary is missing — a
    deployment/config problem, not a per-call failure, so callers should
    surface this distinctly from 'no text found.'"""

    code = ErrorCategory.TOOL_FAILURE

    def __init__(self, detail: str) -> None:
        super().__init__(f"OCR engine unavailable: {detail}")


def _decode_image(image_base64: str) -> Image.Image:
    raw = base64.b64decode(image_base64)
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _validate_languages(languages: tuple[str, ...]) -> str:
    unsupported = [lang for lang in languages if lang not in SUPPORTED_LANGUAGES]
    if unsupported:
        raise ValueError(
            f"Unsupported OCR language(s) {unsupported} — supported: "
            f"{SUPPORTED_LANGUAGES}. Extending this set requires installing "
            "the matching tesseract-ocr-<lang> package (docs/phase-3/OCR.md)."
        )
    return "+".join(languages) if languages else "eng"


class OCREngine:
    def __init__(self, languages: tuple[str, ...] = DEFAULT_LANGUAGES) -> None:
        self._default_lang_string = _validate_languages(languages)

    def extract(
        self,
        image_base64: str,
        *,
        languages: tuple[str, ...] | None = None,
        min_confidence: float = 0.0,
    ) -> list[TextRegion]:
        lang_string = _validate_languages(languages) if languages else self._default_lang_string
        try:
            import pytesseract
        except ImportError as exc:  # pragma: no cover - dependency always installed
            raise OCRUnavailableError("pytesseract is not installed.") from exc

        image = _decode_image(image_base64)
        try:
            data = pytesseract.image_to_data(
                image, lang=lang_string, output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError(
                "the system 'tesseract' binary was not found on PATH."
            ) from exc

        regions: list[TextRegion] = []
        word_count = len(data.get("text", []))
        for i in range(word_count):
            text = data["text"][i].strip()
            if not text:
                continue
            # tesseract reports -1 confidence for non-text structural
            # lines; never treat that as a real (low) confidence score.
            raw_conf = data["conf"][i]
            try:
                raw_conf_f = float(raw_conf)
            except (TypeError, ValueError):
                continue
            if raw_conf_f < 0:
                continue
            confidence = max(0.0, min(1.0, raw_conf_f / 100.0))
            if confidence < min_confidence:
                continue
            regions.append(
                TextRegion(
                    text=text,
                    confidence=confidence,
                    bounds=Rect(
                        left=int(data["left"][i]),
                        top=int(data["top"][i]),
                        width=int(data["width"][i]),
                        height=int(data["height"][i]),
                    ),
                    language=lang_string,
                )
            )
        return regions
