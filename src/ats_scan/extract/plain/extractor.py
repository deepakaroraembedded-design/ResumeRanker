"""Plain-text, Markdown and HTML text extractors (C-03)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from ats_scan.codes import ReasonCode
from ats_scan.extract.plain._html import html_to_text
from ats_scan.extract.plain._langdetect import detect_language
from ats_scan.extract.plain._normalise import normalise_text
from ats_scan.extract.registry import extractor
from ats_scan.models.common import Diagnostic, StageResult
from ats_scan.models.run import RunContext
from ats_scan.models.source import ExtractedText, ExtractionMetadata, SourceDocument, TextBlock
from ats_scan.protocols import TextExtractor


def _read_text(path: str) -> str:
    """Read *path* as text, tolerating binary documents by replacement."""
    raw = Path(path).read_bytes()
    # Prefer UTF-8; fall back to latin-1 so every byte maps to a code point.
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _supported_languages() -> tuple[str, ...]:
    """Return the configured accepted language set, defaulting to English.

    Note: extraction configuration is not currently reachable through
    ``RunContext.config`` (which only carries ``IngestConfig``).  Contract change
    C-03-002 requests that path.  Until it is merged, the environment variable
    ``ATS_SCAN_LANGUAGES`` (comma-separated) or the English default is used.
    """
    env = os.environ.get("ATS_SCAN_LANGUAGES", "en")
    return tuple(lang.strip() for lang in env.split(",") if lang.strip()) or ("en",)


def _make_result(
    doc: SourceDocument,
    raw_text: str,
    method: str,
    ctx: RunContext,
) -> StageResult[ExtractedText]:
    """Normalise *raw_text*, detect language, and package the result."""
    text = normalise_text(raw_text)
    supported = _supported_languages()
    language, language_confidence = detect_language(text, supported)
    metadata = ExtractionMetadata(
        method=method,
        chars_per_page=float(len(text)) if doc.pages in (None, 0) else len(text) / doc.pages,
        language=language,
        language_confidence=language_confidence,
        quality=1.0,
        ocr_confidence=None,
        columns_detected=None,
    )
    diagnostics: list[Diagnostic] = []
    if language not in supported:
        diagnostics.append(
            Diagnostic(
                stage="S2",
                code=ReasonCode.LANG_UNSUPPORTED,
                message=f"Primary language '{language}' is not in the configured set.",
            )
        )
    block = TextBlock(text=text, page=0, bbox=(0.0, 0.0, 0.0, 0.0))
    return StageResult(
        value=ExtractedText(
            text=text,
            metadata=metadata,
            blocks=(block,),
            language=language,
            language_confidence=language_confidence,
        ),
        diagnostics=tuple(diagnostics),
    )


@extractor
class PlainTextExtractor(TextExtractor):
    """Extractor for ``.txt`` and ``.md`` files."""

    media_types: ClassVar[frozenset[str]] = frozenset({"text/plain"})

    def supports(self, doc: SourceDocument) -> bool:
        return doc.media_type in self.media_types or doc.path.lower().endswith(".txt")

    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        raw_text = _read_text(doc.path)
        return _make_result(doc, raw_text, "txt", ctx)


@extractor
class MarkdownExtractor(TextExtractor):
    """Extractor for Markdown files (treated as plain text with block structure)."""

    media_types: ClassVar[frozenset[str]] = frozenset({"text/markdown"})

    def supports(self, doc: SourceDocument) -> bool:
        return doc.media_type in self.media_types or doc.path.lower().endswith(".md")

    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        raw_text = _read_text(doc.path)
        return _make_result(doc, raw_text, "md", ctx)


@extractor
class HtmlExtractor(TextExtractor):
    """Extractor for HTML files, stripping markup while preserving block structure."""

    media_types: ClassVar[frozenset[str]] = frozenset(
        {"text/html", "application/xhtml+xml", "application/html"}
    )

    def supports(self, doc: SourceDocument) -> bool:
        return doc.media_type in self.media_types or doc.path.lower().endswith(
            (".html", ".htm", ".xhtml")
        )

    def extract(self, doc: SourceDocument, ctx: RunContext) -> StageResult[ExtractedText]:
        raw_text = _read_text(doc.path)
        text = html_to_text(raw_text)
        return _make_result(doc, text, "html", ctx)
