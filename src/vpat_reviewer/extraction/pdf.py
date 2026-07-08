"""PDF extractor (pdfplumber). Behavior relocated verbatim from the v10 parser."""

from __future__ import annotations

import logging

from vpat_reviewer.extraction.base import RawDocument, Table

logger = logging.getLogger(__name__)


class PdfExtractor:
    extensions: tuple[str, ...] = (".pdf",)

    def extract(self, path: str) -> RawDocument:
        try:
            import pdfplumber

            pages_text: list[str] = []
            all_tables: list[Table] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
                    tbls = page.extract_tables()
                    if tbls:
                        all_tables.extend(tbls)
            return RawDocument("\n".join(pages_text), all_tables)
        except Exception as e:  # noqa: BLE001 — extraction failure must not crash.
            logger.warning("PDF extraction error: %s", e)
            return RawDocument("", [])
