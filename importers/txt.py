"""
Plain-text importer.

Reads a .txt file as UTF-8 and hands its contents to the tokenizer.
Falls back to latin-1 on decode errors so legacy files do not crash
the app; the spec accepts minor garbling from encoding guesses in
Phase 1.
"""

from pathlib import Path

from core.tokenizer import Token, tokenize
from importers.base import Importer


class TxtImporter(Importer):

    @property
    def extensions(self) -> tuple[str, ...]:
        return (".txt",)

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def load(self, path: Path) -> tuple[str, list[Token]]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Some older .txt files are Windows-1252 or similar. latin-1
            # never raises, so this is a safe last resort even if a few
            # characters end up wrong.
            text = path.read_text(encoding="latin-1")
        return text, tokenize(text)
