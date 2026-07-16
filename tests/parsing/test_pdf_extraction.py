"""Coverage for the PDF extractor (``extraction/pdf.py``).

Three layers, no mocks (matching the repo's real-fixture philosophy):

* ``_overlay_fonts`` — the watermark-drop geometry — is unit-tested with
  synthetic pdfplumber-shaped char dicts, since a diagonally-stamped preview
  overlay is impractical to author as a real PDF.
* ``_clean`` — is driven with a tiny fake page so both the overlay-filter branch
  and the best-effort error path run.
* ``extract`` — is exercised end-to-end against a real PDF generated with
  ReportLab (text + a bordered table), plus a corrupt file for the failure path.
"""

from pathlib import Path

from reportlab.pdfgen import canvas

from vpat_reviewer.extraction.pdf import PdfExtractor, _overlay_fonts


def _char(font: str, top: float, x0: float, x1: float) -> dict:
    return {"fontname": font, "top": top, "x0": x0, "x1": x1}


def _run_of(font: str, top: float, n: int) -> list[dict]:
    """A left-to-right run of `n` touching chars — the shape of real body text."""
    return [_char(font, top, i * 5.0, i * 5.0 + 5.0) for i in range(n)]


def _scattered(font: str, n: int) -> list[dict]:
    """`n` isolated chars, each on its own line and far apart — an overlay."""
    return [_char(font, i * 50.0, i * 200.0, i * 200.0 + 5.0) for i in range(n)]


# ── _overlay_fonts ───────────────────────────────────────────────────────────


def test_overlay_fonts_empty_page():
    assert _overlay_fonts([]) == set()


def test_overlay_fonts_flags_a_sparse_isolated_font():
    chars = _run_of("Body", top=100.0, n=40) + _scattered("Watermark", n=8)
    assert _overlay_fonts(chars) == {"Watermark"}


def test_overlay_fonts_leaves_body_text_alone():
    # A single dominant, well-neighboured font is the document's own text.
    assert _overlay_fonts(_run_of("Body", top=100.0, n=40)) == set()


def test_overlay_fonts_ignores_too_few_chars():
    # Below _MIN_CHARS (4) there is too little to judge — a page number, say.
    chars = _run_of("Body", top=100.0, n=40) + _scattered("Tiny", n=3)
    assert "Tiny" not in _overlay_fonts(chars)


def test_overlay_fonts_ignores_a_dominant_font():
    # Even if scattered, a font that is most of the page is content, not overlay.
    assert _overlay_fonts(_scattered("Only", n=10)) == set()


def test_overlay_fonts_keeps_a_minority_but_neighboured_font():
    # A minority font whose chars still sit together (a caption or sidebar) is
    # content, not a watermark. This is the case that exercises the actual
    # neighbour-detection: it's evaluated (not dominant) yet has adjacent chars.
    chars = _run_of("Body", top=100.0, n=40) + _run_of("Caption", top=300.0, n=8)
    assert _overlay_fonts(chars) == set()


# ── _clean ───────────────────────────────────────────────────────────────────


class _FakePage:
    def __init__(self, chars: list[dict], raise_it: bool = False) -> None:
        self.chars = chars
        self._raise = raise_it
        self.filter_pred = None

    def dedupe_chars(self):
        if self._raise:
            raise RuntimeError("boom")
        return self

    def filter(self, pred):
        self.filter_pred = pred
        return self


def test_clean_filters_out_overlay_chars():
    chars = _run_of("Body", top=100.0, n=40) + _scattered("Watermark", n=8)
    page = _FakePage(chars)
    PdfExtractor()._clean(page)
    assert page.filter_pred is not None, "an overlay font should trigger a filter"
    # The predicate keeps body chars and drops the overlay font.
    assert page.filter_pred({"fontname": "Body"}) is True
    assert page.filter_pred({"fontname": "Watermark"}) is False


def test_clean_is_best_effort_on_error():
    page = _FakePage([], raise_it=True)
    # A cleanup failure must not propagate — the original page is returned.
    assert PdfExtractor()._clean(page) is page


# ── extract (end-to-end on a real PDF) ───────────────────────────────────────


def _make_pdf(path: Path, text: str = "Accessibility Conformance Report") -> None:
    c = canvas.Canvas(str(path))
    c.drawString(72, 740, text)
    # A bordered 2x2 grid so pdfplumber resolves a table from the ruling lines.
    cells = [["Criteria", "Status"], ["1.1.1 Non-text Content", "Supports"]]
    x0, y0, w, h = 72, 650, 220, 30
    for r, row in enumerate(cells):
        for col, val in enumerate(row):
            cx, cy = x0 + col * w, y0 - r * h
            c.rect(cx, cy, w, h)
            c.drawString(cx + 4, cy + h - 14, val)
    c.showPage()
    c.save()


def test_extract_reads_text_and_tables(tmp_path: Path):
    pdf = tmp_path / "vpat.pdf"
    _make_pdf(pdf)
    raw = PdfExtractor().extract(str(pdf))

    assert "Accessibility Conformance Report" in raw.text
    assert not raw.is_empty
    # The bordered grid should resolve to a table containing our cell text.
    flat = [str(cell) for table in raw.tables for row in table for cell in row]
    assert any("Supports" in c for c in flat), f"table not extracted: {raw.tables}"


def test_extract_corrupt_file_returns_empty(tmp_path: Path):
    bad = tmp_path / "not-really.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not a valid pdf body")
    raw = PdfExtractor().extract(str(bad))
    # Extraction failure is swallowed into an empty document, never a crash.
    assert raw.is_empty
    assert raw.tables == []


def test_extract_missing_file_returns_empty(tmp_path: Path):
    raw = PdfExtractor().extract(str(tmp_path / "nope.pdf"))
    assert raw.is_empty
