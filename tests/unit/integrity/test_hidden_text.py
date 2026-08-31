from __future__ import annotations

import pytest
from tests.unit.integrity.conftest import extracted_text, source_doc

from resume_ranker.integrity.hidden_text import HiddenTextDetector
from resume_ranker.models.config import IntegrityConfig
from resume_ranker.models.source import TextBlock


def _visible_block(text: str) -> TextBlock:
    return TextBlock(
        text=text,
        page=1,
        bbox=(0.0, 0.0, 1.0, 1.0),
        colour=(0.0, 0.0, 0.0),
        font_size=12.0,
    )


def _hidden_colour_block(text: str) -> TextBlock:
    return TextBlock(
        text=text,
        page=1,
        bbox=(0.0, 0.0, 1.0, 1.0),
        colour=(1.0, 1.0, 1.0),
        font_size=12.0,
    )


def _hidden_size_block(text: str) -> TextBlock:
    return TextBlock(
        text=text,
        page=1,
        bbox=(0.0, 0.0, 1.0, 1.0),
        colour=(0.0, 0.0, 0.0),
        font_size=2.0,
    )


def _hidden_render_mode_block(text: str) -> TextBlock:
    return TextBlock(
        text=text,
        page=1,
        bbox=(0.0, 0.0, 1.0, 1.0),
        colour=(0.0, 0.0, 0.0),
        font_size=12.0,
        render_mode=3,
    )


def _hidden_off_page_block(text: str) -> TextBlock:
    return TextBlock(
        text=text,
        page=1,
        bbox=(-1.0, -1.0, -0.5, -0.5),
        colour=(0.0, 0.0, 0.0),
        font_size=12.0,
    )


@pytest.mark.parametrize(
    "hidden_block_factory",
    [
        _hidden_colour_block,
        _hidden_size_block,
        _hidden_render_mode_block,
        _hidden_off_page_block,
    ],
)
def test_hidden_block_cues_raise(hidden_block_factory: callable) -> None:
    """Each FR-1101 cue is enough to raise HIDDEN_TEXT when the share is high."""
    text = extracted_text(
        _visible_block("Normal text."),
        hidden_block_factory("Python Java Ruby"),
    )
    findings = HiddenTextDetector().inspect(source_doc(), text, None)
    assert len(findings) == 1
    assert findings[0].code == "HIDDEN_TEXT"
    assert len(findings[0].spans) == 1
    assert findings[0].quotes[0] == "Python Java Ruby"


def test_hidden_share_below_threshold_is_clean() -> None:
    """A single hidden token in a long visible text stays below the 15% default."""
    text = extracted_text(
        _visible_block("one two three four five six seven eight nine ten."),
        _hidden_colour_block("Python"),
    )
    findings = HiddenTextDetector().inspect(source_doc(), text, None)
    assert not findings


def test_low_threshold_catches_single_hidden_token() -> None:
    """A lower threshold turns a small hidden token into a finding."""
    config = IntegrityConfig(hidden_text_token_delta_share=0.05)
    text = extracted_text(
        _visible_block("one two three four five six seven eight nine ten."),
        _hidden_colour_block("Python"),
    )
    findings = HiddenTextDetector(config).inspect(source_doc(), text, None)
    assert len(findings) == 1


def test_no_blocks_is_clean() -> None:
    """An ExtractedText with no blocks produces no findings."""
    text = extracted_text()
    findings = HiddenTextDetector().inspect(source_doc(), text, None)
    assert not findings


def test_multiple_hidden_spans_reported() -> None:
    """All hidden blocks are listed in the finding."""
    text = extracted_text(
        _visible_block("Normal resume text."),
        _hidden_colour_block("Python"),
        _hidden_colour_block("Java"),
    )
    findings = HiddenTextDetector().inspect(source_doc(), text, None)
    assert len(findings) == 1
    assert len(findings[0].spans) == 2
    assert set(findings[0].quotes) == {"Python", "Java"}
