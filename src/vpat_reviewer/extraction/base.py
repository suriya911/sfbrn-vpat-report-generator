"""The extraction boundary types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# A table is a list of rows; a row is a list of cell strings. Empty cells may be
# ``None`` (as pdfplumber emits); the parsing layer coerces ``None`` -> "".
Table = list[list[str | None]]


@dataclass(frozen=True)
class RawDocument:
    """Raw text and tables extracted from a source file, before any parsing."""

    text: str
    tables: list[Table]

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@runtime_checkable
class Extractor(Protocol):
    """Reads one or more file formats into a :class:`RawDocument`."""

    #: File extensions (lowercase, incl. dot) this extractor handles.
    extensions: tuple[str, ...]

    def extract(self, path: str) -> RawDocument: ...
