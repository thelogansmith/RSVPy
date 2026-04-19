"""
Importer interface.
 
Every file-format handler in RSVPy implements this interface. The UI
layer iterates over the registered importers, asks each whether it can
handle a given path, and uses the first match to load the file into
a canonical text string plus its tokenized form. This keeps the UI
ignorant of format-specific details and makes adding new formats (epub,
docx, pdf) a single-file change.
 
The canonical text is what the tokenizer was given. Downstream features
(Phase 2 fingerprinting, Phase 3 context window) need that same string
so token source offsets line up.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from core.tokenizer import Token


class Importer(ABC):
    """Abstract base for all file-format importers."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Return True if this importer knows how to load the given file."""

    @abstractmethod
    def load(self, path: Path) -> tuple[str, list[Token]]:
        """Read the file and return (canonical_text, tokens).
 
        canonical_text is the exact string passed to tokenize(); tokens'
        source_start / source_end fields index into that string.
        """
    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        """File extensions this importer supports, e.g. ('.txt',).

        Used to build the file dialog's type filter. Extensions should
        include the leading dot and be lowercase.
        """
