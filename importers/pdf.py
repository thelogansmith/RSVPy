"""
PDF importer.

Uses pdfplumber to extract text from text-based PDF files page by
page. Pages are joined with double newlines so the tokenizer detects
page boundaries as paragraph breaks.

Known limitations (acceptable for Phase 3):
  - Multi-column layouts may interleave columns incorrectly.
  - Tables may extract with garbled structure.
  - Math, diagrams, and images are silently skipped.
  - Scanned / image-only pages produce no text (skipped).
  - Password-protected PDFs raise an exception, handled by the
    caller's broad except in _load_file.

Requires: pdfplumber (listed in requirements.txt).
"""

from pathlib import Path

import pdfplumber

from core.tokenizer import Token, tokenize
from importers.base import Importer


def extract_preview(path: Path, max_pages: int = 3) -> tuple[str, int]:
    """Extract text from the first few pages for the preview dialog.

    Returns (preview_text, total_page_count). Runs on the main thread
    since it only touches a handful of pages and is fast enough.
    """
    with pdfplumber.open(str(path)) as pdf:
        total = len(pdf.pages)
        parts: list[str] = []
        for page in pdf.pages[:max_pages]:
            text = page.extract_text()
            if text and text.strip():
                parts.append(text.strip())
        return "\n\n".join(parts), total


def _extract_full_text(path: Path) -> str:
    """Extract text from every page of the PDF."""
    with pdfplumber.open(str(path)) as pdf:
        parts: list[str] = []
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts)


class PdfImporter(Importer):

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".pdf",)

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: Path) -> tuple[str, list[Token]]:
        canonical = _extract_full_text(path)
        return canonical, tokenize(canonical)
