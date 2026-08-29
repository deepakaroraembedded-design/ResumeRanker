"""HTML-to-text conversion preserving block structure."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """Collect text from HTML, inserting paragraph breaks at block elements."""

    _BLOCK_TAGS: frozenset[str] = frozenset(
        {
            "address",
            "article",
            "aside",
            "blockquote",
            "br",
            "caption",
            "dd",
            "div",
            "dt",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "li",
            "main",
            "nav",
            "p",
            "pre",
            "section",
            "table",
            "tbody",
            "td",
            "tfoot",
            "th",
            "thead",
            "tr",
        }
    )

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._pending_space = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._flush_space()
            if self._chunks and not self._chunks[-1].endswith("\n"):
                self._chunks.append("\n")
            if tag == "br":
                self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._flush_space()
            if self._chunks and not self._chunks[-1].endswith("\n"):
                self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            if self._pending_space and self._chunks:
                self._chunks.append(" ")
            self._chunks.append(text)
            self._pending_space = True

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth:
            return
        self._handle_char(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if self._skip_depth:
            return
        self._handle_char(unescape(f"&#{name};"))

    def _handle_char(self, text: str) -> None:
        if text and not text.isspace():
            if self._pending_space and self._chunks:
                self._chunks.append(" ")
            self._chunks.append(text)
            self._pending_space = True
        elif text:
            self._pending_space = True

    def _flush_space(self) -> None:
        self._pending_space = False

    def text(self) -> str:
        text = "".join(self._chunks)
        return text.strip()


def html_to_text(html: str) -> str:
    """Return plain text extracted from *html* with block structure preserved.

    Script and style blocks are removed.  Block elements are normalised to
    paragraph breaks so the downstream structurer can still detect headings
    and sections.

    Args:
        html: Raw HTML markup.

    Returns:
        Plain text with paragraph breaks.
    """
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()
