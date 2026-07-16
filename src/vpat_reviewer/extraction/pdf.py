"""PDF extractor (pdfplumber)."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from vpat_reviewer.extraction.base import RawDocument, Table

logger = logging.getLogger(__name__)

# A char is "beside" another if their boxes very nearly touch.
_ADJACENT_GAP = 3.0
# Chars within this vertical distance are treated as sharing a line.
_LINE_BAND = 2.0
# A font must be at least this scattered, and no more common than this, before
# it is judged an overlay rather than content.
_MAX_NEIGHBOURED = 0.5
_MAX_PAGE_SHARE = 0.25
_MIN_CHARS = 4


def _overlay_fonts(chars: list[dict[str, Any]]) -> set[str]:
    """Fonts on this page that are stamped over the content rather than part of it.

    Documents shared for review often carry a preview/DRM watermark (a Box
    overlay, in one real VPAT). It is drawn diagonally across the page, so its
    characters land inside table cells and interleave with the real text --
    "Not Applicable" comes back as "Not Appdlicable", which no amount of
    downstream cleanup can undo.

    The tell is geometric, not typographic: running text has neighbours to its
    left and right on the same line, whereas a diagonal overlay's characters
    each sit alone. So rather than hardcoding a font name, treat a font as an
    overlay when it is both uncommon on the page and mostly made of isolated
    characters.
    """
    if not chars:
        return set()

    by_font: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in chars:
        by_font[str(c.get("fontname") or "")].append(c)

    overlay: set[str] = set()
    for font, font_chars in by_font.items():
        if len(font_chars) < _MIN_CHARS:
            continue  # too little to judge; a page number is not a watermark.
        if len(font_chars) / len(chars) > _MAX_PAGE_SHARE:
            continue  # a dominant font is the document's own text.

        bands: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for c in font_chars:
            bands[int(float(c["top"]) // _LINE_BAND)].append(c)

        neighboured: set[int] = set()
        for band in bands.values():
            band.sort(key=lambda c: float(c["x0"]))
            for left, right in zip(band, band[1:], strict=False):
                if float(right["x0"]) - float(left["x1"]) < _ADJACENT_GAP:
                    neighboured.add(id(left))
                    neighboured.add(id(right))

        if len(neighboured) / len(font_chars) < _MAX_NEIGHBOURED:
            overlay.add(font)

    return overlay


class PdfExtractor:
    extensions: tuple[str, ...] = (".pdf",)

    def extract(self, path: str) -> RawDocument:
        try:
            import pdfplumber

            pages_text: list[str] = []
            all_tables: list[Table] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page = self._clean(page)
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

    def _clean(self, page: Any) -> Any:
        """Drop rendering artifacts that would otherwise land inside cells."""
        try:
            # Word emits doubled glyphs for faux-bold, which yields "SSuuppoorrttss".
            page = page.dedupe_chars()
            fonts = _overlay_fonts(page.chars)
            if fonts:
                logger.debug("Filtering overlay fonts on page: %s", sorted(fonts))
                # Only chars carry a fontname; ruling lines and rects have none,
                # so they survive the filter and tables still resolve.
                page = page.filter(lambda obj: str(obj.get("fontname") or "") not in fonts)
        except Exception as e:  # noqa: BLE001 — cleanup is best-effort.
            logger.debug("Page cleanup skipped: %s", e)
        return page
