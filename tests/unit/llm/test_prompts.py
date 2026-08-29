from __future__ import annotations

import pytest

from ats_scan.llm.prompts import (
    PromptTemplate,
    list_templates,
    load_template,
    render,
)
from ats_scan.llm.security import remove_quarantined_spans, strip_control_chars


class TestListTemplates:
    def test_discovers_all_templates(self) -> None:
        names = list_templates()
        assert set(names) >= {"E-PARSE", "E-JD", "R-SEM", "R-TRANS", "G-EXPL"}


class TestLoadTemplate:
    def test_loads_latest_version(self) -> None:
        tmpl = load_template("E-PARSE")
        assert tmpl.name == "E-PARSE"
        assert tmpl.version == "1"
        assert "$schema" in tmpl.text
        assert "$nonce" in tmpl.text

    def test_unknown_template_raises(self) -> None:
        with pytest.raises(KeyError):
            load_template("NOT-A-TEMPLATE")


class TestRender:
    def test_substitutes_variables(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="Hello $name!")
        rendered, _ = render(tmpl, {"name": "World"}, nonce="abc")
        assert rendered == "Hello World!"

    def test_includes_nonce_and_schema(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$schema\n---BEGIN $nonce---")
        rendered, _ = render(tmpl, {}, nonce="abc", schema_json='{"type":"object"}')
        assert '"type":"object"' in rendered
        assert "---BEGIN abc---" in rendered

    def test_strips_control_characters(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$text")
        rendered, _ = render(tmpl, {"text": "hello\x00\x1bworld"}, nonce="n")
        assert "\x00" not in rendered
        assert "\x1b" not in rendered
        assert "helloworld" in rendered

    def test_strips_bidi_overrides(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$text")
        rendered, _ = render(tmpl, {"text": "hello\u202eworld"}, nonce="n")
        assert "\u202e" not in rendered
        assert "helloworld" in rendered

    def test_truncates_long_content(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$text")
        rendered, _ = render(tmpl, {"text": "x" * 1000}, nonce="n", max_content_length=10)
        assert rendered == "x" * 10

    def test_removes_quarantined_spans(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$text")
        text = "hello malicious world"
        rendered, source = render(
            tmpl,
            {"text": text},
            nonce="n",
            quarantined_spans=[(6, 16)],
        )
        assert source == "hello world"
        assert "malicious" not in rendered

    def test_returns_source_text(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$text")
        rendered, source = render(tmpl, {"text": "source"}, nonce="n")
        assert source == "source"

    def test_no_source_text(self) -> None:
        tmpl = PromptTemplate(name="test", version="1", text="$jd_text")
        rendered, source = render(tmpl, {"jd_text": "jd"}, nonce="n")
        assert source is None


class TestStripControlChars:
    def test_keeps_whitespace_and_printable(self) -> None:
        assert strip_control_chars("a b\t\n\rc") == "a b\t\n\rc"

    def test_removes_null_and_escape(self) -> None:
        assert strip_control_chars("a\x00b\x1bc") == "abc"


class TestRemoveQuarantinedSpans:
    def test_removes_single_span(self) -> None:
        assert remove_quarantined_spans("hello world", [(6, 11)]) == "hello "

    def test_clamps_out_of_bounds(self) -> None:
        assert remove_quarantined_spans("hi", [(-5, 100)]) == ""

    def test_no_spans_unchanged(self) -> None:
        assert remove_quarantined_spans("hi", []) == "hi"
