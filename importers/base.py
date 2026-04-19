"""
Importer interface.

Every file-format handler in RSVPy implements this interface. The UI
layer iterates over the registered importers, asks each whether it can
handle a given path, and uses the first match to load the file into a
list of Tokens. This keeps the UI ignorant of format-specific details
and makes adding new formats (epub, docx, pdf) a single-file change.
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
    def load(self, path: Path) -> list[Token]:
        """Read the file and return its tokenized contents."""

    @property
    @abstractmethod
    def extensions(self) -> tuple[str, ...]:
        """File extensions this importer supports, e.g. ('.txt',).

        Used to build the file dialog's type filter. Extensions should
        include the leading dot and be lowercase.
        """
