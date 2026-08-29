from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.integrity.conftest import (
    ADVERSARIAL_DIR,
    SYNTHETIC_DIR,
    source_doc,
)

from ats_scan.integrity import (
    HiddenTextDetector,
    InjectionDetector,
    KeywordStuffingDetector,
)
from ats_scan.models.source import ExtractedText, ExtractionMetadata, TextBlock


def _read_plain(path: Path) -> ExtractedText:
    content = path.read_text(encoding="utf-8")
    return ExtractedText(
        text=content,
        metadata=ExtractionMetadata(method="fake"),
        blocks=(TextBlock(text=content, page=1, bbox=(0.0, 0.0, 1.0, 1.0)),),
    )


def _read_hidden(path: Path) -> ExtractedText:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    blocks: list[TextBlock] = []
    for i, line in enumerate(lines):
        blocks.append(
            TextBlock(
                text=line,
                page=1,
                bbox=(0.0, 0.0, 1.0, 1.0),
                colour=(1.0, 1.0, 1.0) if i > 0 else (0.0, 0.0, 0.0),
                font_size=12.0,
            )
        )
    return ExtractedText(
        text=content,
        metadata=ExtractionMetadata(method="fake"),
        blocks=tuple(blocks),
    )


@pytest.mark.adversarial
@pytest.mark.parametrize("path", sorted(ADVERSARIAL_DIR.glob("adversarial_00*_injection.md")))
def test_injection_recall(path: Path) -> None:
    """TRD §13.3: injection recall >= 0.98 (four fixtures, all must hit)."""
    text = _read_plain(path)
    findings = InjectionDetector().inspect(source_doc(str(path)), text, None)
    assert findings, f"Injection missed in {path.name}"
    assert findings[0].code == "INJECTION_ATTEMPT"
    assert findings[0].spans


@pytest.mark.adversarial
@pytest.mark.parametrize("path", sorted(ADVERSARIAL_DIR.glob("adversarial_00*_stuffing.md")))
def test_stuffing_recall(path: Path) -> None:
    """Every keyword-stuffing fixture must be detected."""
    text = _read_plain(path)
    findings = KeywordStuffingDetector().inspect(source_doc(str(path)), text, None)
    assert findings, f"Stuffing missed in {path.name}"
    assert findings[0].code == "KEYWORD_STUFFING"


@pytest.mark.adversarial
@pytest.mark.parametrize("path", sorted(ADVERSARIAL_DIR.glob("adversarial_00*_hidden.md")))
def test_hidden_text_recall(path: Path) -> None:
    """TRD §13.3: hidden-text recall >= 0.95 (four fixtures, all must hit)."""
    text = _read_hidden(path)
    findings = HiddenTextDetector().inspect(source_doc(str(path)), text, None)
    assert findings, f"Hidden text missed in {path.name}"
    assert findings[0].code == "HIDDEN_TEXT"


@pytest.mark.adversarial
def test_clean_resumes_produce_zero_findings() -> None:
    """The 40 synthetic fixture resumes must not trigger any integrity flag."""
    paths = sorted(SYNTHETIC_DIR.glob("*.md"))
    assert len(paths) == 40
    detectors = [
        HiddenTextDetector(),
        KeywordStuffingDetector(),
        InjectionDetector(),
    ]
    for path in paths:
        text = _read_plain(path)
        for detector in detectors:
            findings = detector.inspect(source_doc(str(path)), text, None)
            assert not findings, f"{detector.code} false positive on {path.name}: {findings}"
