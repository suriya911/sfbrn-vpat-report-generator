"""Plain-text extractor."""

from __future__ import annotations

import logging

from vpat_reviewer.extraction.base import RawDocument

logger = logging.getLogger(__name__)


class TxtExtractor:
    extensions: tuple[str, ...] = (".txt",)

    def extract(self, path: str) -> RawDocument:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return RawDocument(f.read(), [])
        except Exception as e:  # noqa: BLE001 — extraction failure must not crash.
            logger.warning("TXT read error: %s", e)
            return RawDocument("", [])
