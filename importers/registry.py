"""
Importer registry.

Central place to list every available importer. The UI asks this
module for an importer that can handle a path, and for the set of
extensions to show in the file dialog. Adding a new format means:
write the importer, import it here, add it to the list. Nothing
else changes.
"""

from pathlib import Path

from importers.base import Importer
from importers.docx import DocxImporter
from importers.epub import EpubImporter
from importers.md import MarkdownImporter
from importers.txt import TxtImporter


# Order matters: the first importer whose can_handle returns True wins.
_IMPORTERS: list[Importer] = [
    TxtImporter(),
    MarkdownImporter(),
    DocxImporter(),
    EpubImporter(),
]


def find_importer(path: Path) -> Importer | None:
    """Return the first registered importer that can handle `path`."""
    for importer in _IMPORTERS:
        if importer.can_handle(path):
            return importer
    return None


def all_extensions() -> tuple[str, ...]:
    """Return every extension supported by any registered importer."""
    exts: list[str] = []
    for importer in _IMPORTERS:
        exts.extend(importer.extensions)
    return tuple(exts)