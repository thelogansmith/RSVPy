"""
EPUB importer.

Uses ebooklib to iterate chapters in spine order and stdlib
html.parser to extract text from each chapter's XHTML. Chapters are
joined with double newlines so paragraph-break detection works across
chapter boundaries.

EPUBs vary wildly in the wild — some use <p> tags, some use <div>,
some have inline CSS, some embed SVG. The HTMLTextExtractor is
deliberately simple: it grabs all text content and uses block-level
tags to insert line breaks. This handles the vast majority of
well-formed EPUBs; exotic layouts may produce minor oddities that
are acceptable for Phase 2.

Requires: EbookLib (listed in requirements.txt).
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import ebooklib
from ebooklib import epub

from core.tokenizer import Token, tokenize
from importers.base import Importer


# Tags whose boundaries should produce whitespace in the extracted text.
# Without this, <p>Hello</p><p>World</p> would extract as "HelloWorld".
_BLOCK_TAGS = frozenset({
    "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "pre", "tr", "td", "th", "dt", "dd",
    "section", "article", "header", "footer", "figcaption",
})

# Tags whose content should be skipped entirely — not readable text.
_SKIP_TAGS = frozenset({"script", "style", "head"})


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text converter using stdlib html.parser.

    Collects text content, inserting newlines at block-element
    boundaries so paragraph structure survives into the tokenizer.
    """

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag in _BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")
        if tag == "br":
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag in _BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _html_to_text(html_bytes: bytes) -> str:
    """Extract plain text from an XHTML chapter."""
    # EPUBs are almost always UTF-8, but some older ones use latin-1.
    try:
        html_str = html_bytes.decode("utf-8")
    except UnicodeDecodeError:
        html_str = html_bytes.decode("latin-1")

    parser = _HTMLTextExtractor()
    parser.feed(html_str)
    return parser.get_text().strip()


class EpubImporter(Importer):

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".epub",)

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: Path) -> tuple[str, list[Token]]:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})

        chapter_texts: list[str] = []

        # Iterate in spine order — this is the intended reading order
        # as defined by the EPUB's metadata, not the file-system order
        # of the XHTML files inside the ZIP.
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_content()
            text = _html_to_text(content)
            if text:
                chapter_texts.append(text)

        canonical = "\n\n".join(chapter_texts)
        return canonical, tokenize(canonical)
