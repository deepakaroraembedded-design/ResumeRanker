from __future__ import annotations

from pathlib import Path

from resume_ranker.models.source import (
    ExtractedText,
    ExtractionMetadata,
    SourceDocument,
    TextBlock,
)

ADVERSARIAL_DIR = Path(__file__).parent.parent.parent / "corpus" / "resumes" / "adversarial"
SYNTHETIC_DIR = Path(__file__).parent.parent.parent / "corpus" / "resumes" / "synthetic"


def source_doc(path: str = "resume.pdf", media_type: str = "application/pdf") -> SourceDocument:
    """Return a minimal SourceDocument for detector tests."""
    return SourceDocument(
        path=path,
        content_sha256="a" * 64,
        bytes=1,
        mtime="2026-01-01",
        media_type=media_type,
    )


def extracted_text(*blocks: TextBlock) -> ExtractedText:
    """Build an ExtractedText whose text is the block texts joined by newlines."""
    text = "\n".join(block.text for block in blocks)
    return ExtractedText(
        text=text,
        metadata=ExtractionMetadata(method="fake"),
        blocks=blocks,
    )
