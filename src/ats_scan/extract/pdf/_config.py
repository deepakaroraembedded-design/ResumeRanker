from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ats_scan.models.config import IngestConfig


@dataclass(frozen=True)
class PdfExtractionConfig:
    """Runtime extraction settings for PDF parsing.

    Defaults mirror the TRD: 120 characters per page for OCR fallback
    (FR-201) and a maximum of 2 concurrent OCR pages (TRD §10.2).
    """

    chars_per_page_threshold: int = 120
    ocr_concurrency: int = 2
    max_pages: int | None = None
    header_footer_margin_share: float = 0.08
    header_footer_min_pages: int = 2
    header_footer_min_share: float = 0.5
    column_gap_share: float = 0.04
    table_min_rows: int = 1
    ocr_dpi: int = 300
    ocr_languages: tuple[str, ...] = ("eng",)
    accepted_languages: tuple[str, ...] = ("en",)
    low_ocr_confidence_threshold: float = 0.5


def build_config(ctx_config: Any) -> PdfExtractionConfig:
    """Build a PDF extraction config from the run context.

    The run context may carry either an ``IngestConfig`` (which only exposes
    page limits) or a full ``RootConfig`` (which may contain an ``extraction``
    dictionary).  In both cases we keep the component defaults for anything not
    explicitly provided.
    """
    cfg = PdfExtractionConfig()
    max_pages: int | None = None
    if ctx_config is not None:
        if isinstance(ctx_config, IngestConfig):
            max_pages = ctx_config.max_pages
        else:
            max_pages = getattr(ctx_config, "max_pages", None)
            if not isinstance(max_pages, int):
                max_pages = None
            extraction = getattr(ctx_config, "extraction", None)
            if isinstance(extraction, dict):
                field_names = frozenset(PdfExtractionConfig.__dataclass_fields__)
                overrides = {key: value for key, value in extraction.items() if key in field_names}
                cfg = replace(cfg, **overrides)
    if cfg.max_pages is None and max_pages is not None:
        cfg = replace(cfg, max_pages=max_pages)
    return cfg
