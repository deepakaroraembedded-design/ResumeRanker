from __future__ import annotations

import io
import warnings
from pathlib import Path

import pymupdf as fitz
import pytest
from PIL import Image, ImageDraw, ImageFont

from ats_scan.extract import load_extractors
from ats_scan.extract.pdf import PdfExtractor, render_page_tokens
from ats_scan.extract.pdf._config import PdfExtractionConfig
from ats_scan.extract.pdf._normalize import normalize_text
from ats_scan.models.run import RunContext
from ats_scan.models.scoring import Evidence
from ats_scan.models.source import SourceDocument
from ats_scan.protocols import TextExtractor

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _make_source(path: Path) -> SourceDocument:
    return SourceDocument(
        path=str(path),
        content_sha256="a" * 64,
        bytes=path.stat().st_size,
        mtime="2026-01-01T00:00:00",
        media_type="application/pdf",
    )


def _write_text_pdf(tmp_path: Path, lines: list[str]) -> Path:
    path = tmp_path / "text.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 700
    for line in lines:
        page.insert_text((50, y), line, fontsize=12, color=(0, 0, 0))
        y -= 30
    doc.save(path)
    doc.close()
    return path


def _write_two_column_pdf(tmp_path: Path, left: list[str], right: list[str]) -> Path:
    path = tmp_path / "two_column.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for i, line in enumerate(left):
        page.insert_text((50, 700 - i * 30), line, fontsize=12, color=(0, 0, 0))
    for i, line in enumerate(right):
        page.insert_text((300, 700 - i * 30), line, fontsize=12, color=(0, 0, 0))
    doc.save(path)
    doc.close()
    return path


def _write_table_pdf(tmp_path: Path, rows: list[list[str]]) -> Path:
    path = tmp_path / "table.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    cell_width = 100
    cell_height = 30
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            x0 = 50 + c * cell_width
            y0 = 650 - r * cell_height
            y1 = y0 + cell_height
            page.insert_text((x0 + 5, y0 + cell_height - 5), text, fontsize=12, color=(0, 0, 0))
            page.draw_rect(fitz.Rect(x0, y0, x0 + cell_width, y1), color=(0, 0, 0))
    doc.save(path)
    doc.close()
    return path


def _write_header_footer_pdf(tmp_path: Path, pages: int) -> Path:
    path = tmp_path / "header_footer.pdf"
    doc = fitz.open()
    for p in range(pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 760), "Repeated Header", fontsize=10, color=(0, 0, 0))
        page.insert_text((50, 30), "Repeated Footer", fontsize=10, color=(0, 0, 0))
        page.insert_text((400, 30), str(p + 1), fontsize=10, color=(0, 0, 0))
        page.insert_text((50, 400), f"Body content on page {p + 1}", fontsize=12, color=(0, 0, 0))
    doc.save(path)
    doc.close()
    return path


def _write_encrypted_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "encrypted.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 700), "secret content", fontsize=12, color=(0, 0, 0))
    buf = io.BytesIO()
    doc.save(
        buf,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="user",
    )
    doc.close()
    path.write_bytes(buf.getvalue())
    return path


def _write_corrupt_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4\ninvalid content")
    return path


def _write_hidden_text_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "hidden_text.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 700), "Visible text", fontsize=12, color=(0, 0, 0))
    page.insert_text((50, 650), "Hidden text", fontsize=1, color=(1, 1, 1))
    doc.save(path)
    doc.close()
    return path


def _write_scanned_pdf(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "scanned.pdf"
    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 80), text, fill="black", font=font)
    png = io.BytesIO()
    img.save(png, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(0, 500, 612, 700), stream=png.getvalue())
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def run_context() -> RunContext:
    return RunContext(run_id="r1")


@pytest.fixture
def low_threshold_config() -> PdfExtractionConfig:
    return PdfExtractionConfig(chars_per_page_threshold=10)


@pytest.fixture
def extractor(low_threshold_config: PdfExtractionConfig) -> PdfExtractor:
    return PdfExtractor(low_threshold_config)


def test_is_text_extractor(extractor: PdfExtractor) -> None:
    assert isinstance(extractor, TextExtractor)


def test_supports_pdf(extractor: PdfExtractor) -> None:
    pdf = SourceDocument(
        path="x.pdf",
        content_sha256="a" * 64,
        bytes=1,
        mtime="2026-01-01",
        media_type="application/pdf",
    )
    assert extractor.supports(pdf) is True


def test_does_not_support_text_plain(extractor: PdfExtractor) -> None:
    txt = SourceDocument(
        path="x.txt",
        content_sha256="a" * 64,
        bytes=1,
        mtime="2026-01-01",
        media_type="text/plain",
    )
    assert extractor.supports(txt) is False


def test_extracts_native_text(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_text_pdf(tmp_path, ["Hello world", "Second line"])
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    assert result.ok
    text = result.value.text if result.value else ""
    assert "Hello world" in text
    assert "Second line" in text
    assert result.value.metadata.method == "pdfplumber"
    assert result.value.metadata.quality == 1.0
    assert result.value.metadata.chars_per_page is not None


def test_block_text_appears_in_final_text(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_text_pdf(tmp_path, ["Line one", "Line two"])
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    for block in result.value.blocks:
        assert block.text in result.value.text


def test_evidence_quote_matches_final_text(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_text_pdf(tmp_path, ["First line", "Second line"])
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    text = result.value.text
    offset = 0
    for index, block in enumerate(result.value.blocks):
        if index > 0:
            offset += 1  # newline separator between blocks
        span = (offset, offset + len(block.text))
        evidence = Evidence(span=span, quote=block.text)
        assert evidence.quote == text[evidence.span[0] : evidence.span[1]]
        offset += len(block.text)


def test_two_column_reading_order(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    left = ["alpha", "bravo", "charlie"]
    right = ["delta", "echo", "foxtrot"]
    path = _write_two_column_pdf(tmp_path, left, right)
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    text = result.value.text
    lines = [line for line in text.splitlines() if line]
    # Column-major order: left column first, then right column.
    assert lines[:3] == left
    assert lines[3:6] == right
    assert result.value.metadata.columns_detected == 2


def test_table_cells_row_wise(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    rows = [["A1", "B1"], ["A2", "B2"], ["A3", "B3"]]
    path = _write_table_pdf(tmp_path, rows)
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    blocks = [b.text for b in result.value.blocks]
    # Cells must be emitted top-to-bottom, left-to-right within each row.
    assert blocks == ["A1", "B1", "A2", "B2", "A3", "B3"]


def test_drops_repeated_headers_and_footers(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_header_footer_pdf(tmp_path, pages=3)
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    text = result.value.text
    assert "Repeated Header" not in text
    assert "Repeated Footer" not in text
    # Footer page numbers should be removed; body text naturally contains digits.
    body_lines = [line for line in text.splitlines() if "Body content" not in line]
    assert not any(line.strip().isdigit() for line in body_lines)
    assert "Body content on page 1" in text
    assert "Body content on page 3" in text


def test_encrypted_pdf_returns_diagnostic(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_encrypted_pdf(tmp_path)
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    assert not result.ok
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "EXT_ENCRYPTED"
    assert diagnostic.stage == "S2"


def test_corrupt_pdf_returns_diagnostic(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_corrupt_pdf(tmp_path)
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    assert not result.ok
    assert any(d.code == "EXT_CORRUPT" for d in result.diagnostics)


def test_unicode_normalization_function() -> None:
    raw = "\ufb01\u200b\u202e\u00adtest"
    cleaned = normalize_text(raw)
    assert "\u200b" not in cleaned
    assert "\u202e" not in cleaned
    assert "\u00ad" not in cleaned
    assert "fi" in cleaned


def test_hidden_text_preserves_glyph_metadata(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_hidden_text_pdf(tmp_path)
    source = _make_source(path)
    result = extractor.extract(source, run_context)
    text = result.value.text
    assert "Visible text" in text
    assert "Hidden text" in text
    blocks = {b.text: b for b in result.value.blocks}
    assert blocks["Hidden text"].font_size == pytest.approx(1.0, abs=0.1)
    assert blocks["Hidden text"].colour == pytest.approx((1.0, 1.0, 1.0), abs=0.01)


def test_render_page_tokens_exposes_glyph_data(
    tmp_path: Path, extractor: PdfExtractor, run_context: RunContext
) -> None:
    path = _write_text_pdf(tmp_path, ["render me"])
    tokens = render_page_tokens(str(path))
    assert len(tokens) > 0
    for token in tokens:
        assert "text" in token
        assert "bbox" in token
        assert "page" in token
    joined = "".join(t["text"] for t in tokens)
    assert "render me" in normalize_text(joined)


def test_registry_contains_pdf_extractors() -> None:
    registry = load_extractors()
    assert "PdfExtractor" in registry
    assert "OcrPdfExtractor" in registry


@pytest.mark.slow
@pytest.mark.parametrize("text", ["OCR works", "123 Scanned"])
def test_ocr_fallback(text: str, tmp_path: Path, run_context: RunContext) -> None:
    path = _write_scanned_pdf(tmp_path, text)
    source = _make_source(path)
    extractor = PdfExtractor()  # default threshold triggers OCR
    result = extractor.extract(source, run_context)
    assert result.ok
    assert text in result.value.text
    assert result.value.metadata.method == "ocrmypdf"
    assert result.value.metadata.ocr_confidence is not None
