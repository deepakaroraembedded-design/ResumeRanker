from __future__ import annotations

from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """A candidate file as discovered by the ingest stage."""

    path: str
    content_sha256: str
    bytes: int = Field(..., ge=0)
    pages: int | None = Field(None, ge=1)
    mtime: str
    media_type: str


class ExtractionMetadata(BaseModel):
    """Quality and method metadata for an extraction."""

    method: str
    chars_per_page: float | None = None
    ocr_confidence: float | None = Field(None, ge=0.0, le=1.0)
    columns_detected: int | None = Field(None, ge=1)
    language: str | None = None
    language_confidence: float | None = Field(None, ge=0.0, le=1.0)
    quality: float | None = Field(None, ge=0.0, le=1.0)


class TextBlock(BaseModel):
    """A contiguous block of extracted text with layout metadata."""

    text: str
    page: int = Field(..., ge=0)
    bbox: tuple[float, float, float, float]
    font_size: float | None = None
    colour: tuple[float, float, float] | None = None
    render_mode: int | None = None


class ExtractedText(BaseModel):
    """Normalised text extracted from a source document."""

    text: str
    metadata: ExtractionMetadata
    blocks: tuple[TextBlock, ...] = ()
    language: str | None = None
    language_confidence: float | None = None
