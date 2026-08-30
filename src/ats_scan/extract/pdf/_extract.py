from __future__ import annotations

from collections.abc import Sequence

import pdfplumber

from ats_scan.extract.pdf._config import PdfExtractionConfig
from ats_scan.extract.pdf._tables import find_table_cells, text_from_table_cell
from ats_scan.extract.pdf._tokens import (
    Glyph,
    LineBlock,
    _drop_repeated_headers_footers,
    _glyphs_from_page,
    _line_blocks_from_glyphs,
)
from ats_scan.models.source import ExtractedText, ExtractionMetadata, TextBlock


def extract_text_from_pdf(
    path: str, config: PdfExtractionConfig, max_pages: int | None = None
) -> ExtractedText:
    """Extract normalised text from a PDF at *path*.

    Tables are emitted row-wise, multi-column text is read column-first, and
    repeated headers/footers are dropped (FR-201--FR-204).
    """
    if max_pages is None:
        max_pages = config.max_pages

    with pdfplumber.open(path) as pdf:
        pages = list(pdf.pages)
        if max_pages is not None:
            pages = pages[:max_pages]

        page_heights: dict[int, float] = {}
        page_widths: dict[int, float] = {}
        all_blocks: list[LineBlock] = []
        max_columns = 1
        any_text_layer = False

        for page_index, page in enumerate(pages, start=1):
            page_width = page.width
            page_height = page.height
            page_heights[page_index] = page_height
            page_widths[page_index] = page_width

            table_cells = find_table_cells(page)
            table_bboxes = [bbox for bbox, _row, _col in table_cells]
            table_blocks: list[LineBlock] = []
            for cell_bbox, _row, _col in table_cells:
                cell_text = text_from_table_cell(page, cell_bbox, page_index)
                if cell_text:
                    any_text_layer = True
                    table_blocks.append(
                        LineBlock(
                            page=page_index,
                            bbox=cell_bbox,
                            text=cell_text,
                            font_size=None,
                            color=None,
                            render_mode=None,
                        )
                    )

            glyphs = _glyphs_from_page(page, page_index)
            any_text_layer = any_text_layer or bool(glyphs)
            non_table_glyphs = [
                g
                for g in glyphs
                if not _bbox_intersects_any(g.x0, g.top, g.x1, g.bottom, table_bboxes)
            ]

            column_count = _count_columns(non_table_glyphs, page_width, config)
            max_columns = max(max_columns, column_count)

            line_blocks = _line_blocks_from_glyphs(non_table_glyphs, page_width, config)
            all_blocks.extend(table_blocks)
            all_blocks.extend(line_blocks)

        all_blocks = _drop_repeated_headers_footers(all_blocks, page_heights, config)
        all_blocks = _drop_page_number_lines(all_blocks, page_heights)

        text, text_blocks = _join_blocks(all_blocks, page_widths, page_heights)

        chars_per_page = _chars_per_page(text, len(pages))
        metadata = ExtractionMetadata(
            method="pdfplumber",
            chars_per_page=chars_per_page,
            ocr_confidence=None,
            columns_detected=max_columns if max_columns > 1 else None,
            language="en",
            language_confidence=0.9 if text else None,
            quality=1.0,
        )
        return ExtractedText(
            text=text,
            metadata=metadata,
            blocks=text_blocks,
        )


def _bbox_intersects_any(
    x0: float,
    top: float,
    x1: float,
    bottom: float,
    bboxes: Sequence[tuple[float, float, float, float]],
) -> bool:
    """Return True when the glyph bbox overlaps any table cell.

    pdfplumber bboxes use ``top`` for the upper boundary (larger value in a
    bottom-origin coordinate system) and ``bottom`` for the lower boundary.
    """
    g_upper = max(top, bottom)
    g_lower = min(top, bottom)
    for bbox in bboxes:
        bx0, bt, bx1, bb = bbox
        c_upper = max(bt, bb)
        c_lower = min(bt, bb)
        if x1 < bx0 or x0 > bx1 or g_lower > c_upper or g_upper < c_lower:
            continue
        return True
    return False


def _count_columns(glyphs: Sequence[Glyph], page_width: float, config: PdfExtractionConfig) -> int:
    """Estimate the number of text columns on a page."""
    if not glyphs:
        return 1
    gap = max(config.column_gap_share * page_width, 2.0)
    sorted_glyphs = sorted(glyphs, key=lambda g: g.x0)
    columns = 1
    previous_x1 = sorted_glyphs[0].x1
    for glyph in sorted_glyphs[1:]:
        if glyph.x0 - previous_x1 > gap:
            columns += 1
        previous_x1 = max(previous_x1, glyph.x1)
    return columns


def _drop_page_number_lines(
    blocks: Sequence[LineBlock], page_heights: dict[int, float]
) -> list[LineBlock]:
    """Drop footer lines that are only page numbers."""
    result: list[LineBlock] = []
    for block in blocks:
        height = page_heights.get(block.page, 0.0)
        if height > 0 and block.bbox[3] < height * 0.08:
            stripped = block.text.strip()
            if stripped.isdigit():
                continue
        result.append(block)
    return result


def _join_blocks(
    blocks: Sequence[LineBlock],
    page_widths: dict[int, float],
    page_heights: dict[int, float],
) -> tuple[str, tuple[TextBlock, ...]]:
    """Concatenate line blocks into a single text and a TextBlock tuple.

    TextBlock bboxes are normalised to the unit square so that downstream
    integrity detectors (which assume a [0,1] media box) can detect off-page
    text without false positives.
    """
    text_parts: list[str] = []
    text_blocks: list[TextBlock] = []
    for block in blocks:
        if not block.text:
            continue
        text_parts.append(block.text)
        width = page_widths.get(block.page, 1.0)
        height = page_heights.get(block.page, 1.0)
        if width <= 0 or height <= 0:
            width = height = 1.0
        x0, upper, x1, lower = block.bbox
        normalised_bbox = (
            x0 / width,
            upper / height,
            x1 / width,
            lower / height,
        )
        text_blocks.append(
            TextBlock(
                text=block.text,
                page=block.page,
                bbox=normalised_bbox,
                font_size=block.font_size,
                colour=block.color,
                render_mode=block.render_mode,
            )
        )
    return "\n".join(text_parts), tuple(text_blocks)


def _chars_per_page(text: str, page_count: int) -> float:
    """Return average characters per page, or 0.0 for an empty document."""
    if page_count <= 0:
        return 0.0
    return len(text) / page_count
