from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import ocrmypdf

from resume_ranker.codes import ReasonCode
from resume_ranker.extract.pdf._config import PdfExtractionConfig, build_config
from resume_ranker.extract.pdf._extract import extract_text_from_pdf
from resume_ranker.extract.registry import extractor
from resume_ranker.models.common import Diagnostic, StageResult
from resume_ranker.models.run import RunContext
from resume_ranker.models.source import ExtractedText, SourceDocument
from resume_ranker.protocols import TextExtractor

logger = logging.getLogger(__name__)


@extractor
class OcrPdfExtractor(TextExtractor):
    """OCR fallback extractor for image-heavy PDFs.

    Uses OCRmyPDF/Tesseract to create a searchable PDF and then runs the same
    text extraction pipeline over the OCR output.  This extractor is intentionally
    not selected by ``supports()``; the primary ``PdfExtractor`` invokes it as a
    fallback (FR-201).
    """

    media_types = frozenset({"application/pdf"})

    def __init__(self, config: PdfExtractionConfig | None = None) -> None:
        self._config = config

    def supports(self, doc: SourceDocument) -> bool:
        """Always return False; this extractor is only used as a fallback."""
        return False

    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        config = self._config if self._config is not None else build_config(ctx.config)
        return _run_ocr(doc.path, config)


def _run_ocr(path: str, config: PdfExtractionConfig) -> StageResult[ExtractedText]:
    """OCR a PDF and return the extracted text, or a diagnostic on failure."""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "ocr.pdf"
            ocrmypdf.ocr(
                Path(path),
                output_path,
                language=",".join(config.ocr_languages),
                force_ocr=True,
                progress_bar=False,
                optimize=0,
                rotate_pages=False,
                deskew=False,
                clean=False,
            )
            extracted = extract_text_from_pdf(str(output_path), config, max_pages=config.max_pages)
    except Exception as exc:  # noqa: BLE001 - fault isolation per document
        logger.exception("OCR failed for %s", path)
        return StageResult(
            value=None,
            diagnostics=(
                Diagnostic(
                    stage="S2",
                    code=ReasonCode.EXT_OCR_LOW_CONFIDENCE,
                    message=f"OCR fallback failed: {exc}",
                ),
            ),
        )

    ocr_text = extracted.text.strip()
    if not ocr_text:
        return StageResult(
            value=None,
            diagnostics=(
                Diagnostic(
                    stage="S2",
                    code=ReasonCode.EXT_OCR_LOW_CONFIDENCE,
                    message="OCR produced no usable text.",
                ),
            ),
        )

    # Estimate OCR quality from the share of alphanumeric characters.
    confidence = _estimate_ocr_confidence(ocr_text)
    metadata = extracted.metadata.model_copy(
        update={
            "method": "ocrmypdf",
            "ocr_confidence": confidence,
            "quality": max(0.0, min(1.0, confidence)),
        }
    )
    if confidence < config.low_ocr_confidence_threshold:
        diagnostic = Diagnostic(
            stage="S2",
            code=ReasonCode.EXT_OCR_LOW_CONFIDENCE,
            message=f"OCR confidence {confidence:.2f} is below the threshold.",
        )
        return StageResult(
            value=extracted.model_copy(update={"metadata": metadata}),
            diagnostics=(diagnostic,),
        )
    return StageResult(value=extracted.model_copy(update={"metadata": metadata}))


def _estimate_ocr_confidence(text: str) -> float:
    """Return a crude OCR confidence estimate based on character classes."""
    if not text:
        return 0.0
    alphanumeric = sum(1 for ch in text if ch.isalnum() or ch.isspace())
    return alphanumeric / len(text)


__all__ = ["OcrPdfExtractor"]
