"""
Markdown importer.

Strips Markdown formatting syntax via regex and tokenizes the
remaining plain text. The goal is readable RSVP output, not a
faithful Markdown parser — edge cases in deeply nested or unusual
Markdown are acceptable losses for Phase 2.

What gets stripped:
  - Image syntax:       ![alt](url) → alt text kept
  - Link syntax:        [text](url) → link text kept
  - Reference links:    [text][ref] → link text kept
  - Code fences:        ```lang ... ``` → contents kept, fences dropped
  - Inline code:        `code` → contents kept, backticks dropped
  - ATX headers:        # through ###### → marker dropped
  - Bold / italic:      **bold**, *italic*, __bold__, _italic_ → text kept
  - Strikethrough:      ~~text~~ → text kept
  - Horizontal rules:   ---, ***, ___ → dropped entirely
  - Blockquote markers: > at line start → dropped

What passes through unchanged:
  - HTML tags (deferred to Phase 5)
  - Table syntax (best-effort: pipes remain but content reads okay)
"""

import re
from pathlib import Path

from core.tokenizer import Token, tokenize
from importers.base import Importer


def strip_markdown(text: str) -> str:
    """Remove Markdown syntax, returning plain text suitable for RSVP."""

    # Code fences: keep contents, drop the ``` lines.
    # Non-greedy match across newlines via re.DOTALL.
    text = re.sub(r"^```[^\n]*\n(.*?)^```\s*$", r"\1",
                  text, flags=re.MULTILINE | re.DOTALL)

    # Images before links so ![alt](url) doesn't partially match [alt](url).
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)

    # Inline links: [text](url) or [text](url "title")
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)

    # Reference-style links: [text][ref] or [text][]
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)

    # Inline code: `code` (single backtick, not fences).
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Horizontal rules: a line that is only ---, ***, or ___ (with
    # optional spaces). Must be checked before bold/italic stripping
    # so *** isn't treated as empty bold.
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)

    # ATX headers: strip leading # markers and optional trailing ones.
    text = re.sub(r"^#{1,6}\s+(.+?)(?:\s+#+)?\s*$", r"\1",
                  text, flags=re.MULTILINE)

    # Bold + italic combined: ***text*** or ___text___
    text = re.sub(r"(\*{3}|_{3})(.+?)\1", r"\2", text)

    # Bold: **text** or __text__
    text = re.sub(r"(\*{2}|_{2})(.+?)\1", r"\2", text)

    # Italic: *text* or _text_ (but not mid-word underscores like
    # foo_bar_baz, which we handle by requiring a word boundary or
    # start-of-line for underscore matches).
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)

    # Strikethrough: ~~text~~
    text = re.sub(r"~~(.+?)~~", r"\1", text)

    # Blockquote markers: > at start of line (possibly nested >>).
    text = re.sub(r"^(?:>\s*)+", "", text, flags=re.MULTILINE)

    # Bullet list markers: -, *, + at start of line followed by space.
    # Numbered list markers: 1. 2. etc. Keep the content.
    text = re.sub(r"^[ \t]*[-*+][ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*\d+\.[ \t]+", "", text, flags=re.MULTILINE)

    # Clean up any leftover reference definitions [ref]: url
    text = re.sub(r"^\[[^\]]+\]:\s+.*$", "", text, flags=re.MULTILINE)

    return text


class MarkdownImporter(Importer):

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".md",)

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: Path) -> tuple[str, list[Token]]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")

        canonical = strip_markdown(text)
        return canonical, tokenize(canonical)
