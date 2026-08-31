from __future__ import annotations

import logging

import pymupdf as fitz

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
class PdfExtractor(TextExtractor):
    """Primary PDF text extractor.

    Extracts the embedded text layer using pdfplumber, preserves reading order
    for multi-column layouts and tables, and falls back to OCR when the text
    layer is too sparse (FR-201).
    """

    media_types = frozenset({"application/pdf"})

    def __init__(self, config: PdfExtractionConfig | None = None) -> None:
        self._config = config

    def supports(self, doc: SourceDocument) -> bool:
        return doc.media_type == "application/pdf"

    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        config = self._config if self._config is not None else build_config(ctx.config)
        if _is_encrypted(doc.path):
            return StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S2",
                        code=ReasonCode.EXT_ENCRYPTED,
                        message="Password-protected PDF; no decryption attempted.",
                    ),
                ),
            )

        try:
            extracted = extract_text_from_pdf(doc.path, config, max_pages=config.max_pages)
        except Exception as exc:  # noqa: BLE001 - fault isolation per document
            logger.exception("PDF extraction failed for %s", doc.path)
            return StageResult(
                value=None,
                diagnostics=(
                    Diagnostic(
                        stage="S2",
                        code=ReasonCode.EXT_CORRUPT,
                        message=f"PDF could not be parsed: {exc}",
                    ),
                ),
            )

        if _needs_ocr(extracted, config):
            from resume_ranker.extract.ocr.extractor import OcrPdfExtractor

            ocr_result = OcrPdfExtractor().extract(doc, ctx)
            if ocr_result.ok:
                return ocr_result
            # Keep the sparse text layer but surface the OCR diagnostic.
            return StageResult(value=extracted, diagnostics=ocr_result.diagnostics)

        return StageResult(value=extracted)


def _is_encrypted(path: str) -> bool:
    """Return True when the PDF at *path* requires a password."""
    try:
        with fitz.open(path) as doc:  # type: ignore[no-untyped-call]
            return bool(doc.is_encrypted)
    except Exception as exc:  # noqa: BLE001 - treat as corrupt, not encrypted
        logger.debug("Could not determine encryption for %s: %s", path, exc)
        return False


def _needs_ocr(extracted: ExtractedText, config: PdfExtractionConfig) -> bool:
    """Check whether the text layer is too sparse to be usable (FR-201)."""
    if not extracted.text.strip():
        return True
    threshold = config.chars_per_page_threshold
    if extracted.metadata.chars_per_page is None:
        return False
    return extracted.metadata.chars_per_page < threshold


__all__ = ["PdfExtractor", "_is_encrypted"]
