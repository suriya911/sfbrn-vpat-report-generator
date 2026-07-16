"""The one-page decision sheet: a second renderer behind the same port.

The full ReportLab report is ~26 pages of evidence. This is the other end of the
scale — what someone approving or rejecting a purchase needs, on one sheet:
the verdict, the score, the impact, the worst barriers, and what to do next.

**One page is the whole contract.** A "summary" that quietly runs onto a second
page is not a summary, so the layout is not trusted to behave: it is rendered,
measured, and re-rendered progressively tighter until it genuinely fits (see
``_TRIM_LEVELS`` and ``render``). Adding a row here means checking it still fits
at the tightest trim, not just on the document you happened to test.

This does not replace the full report — it points at it. Everything that gets
dropped (per-criterion remarks, the WCAG rollup, the 508 tables) is why the full
renderer exists, and the footer says so.
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from vpat_reviewer.reporting.base import ReportInputs

# Palette: deliberately duplicated from reportlab_renderer rather than imported.
# That module is excluded from mypy/ruff (see pyproject) and importing it would
# drag the 83KB layout engine -- and its Any-typed surface -- into this one.
C_PRIMARY = colors.HexColor("#1a4f8a")
C_BG = colors.HexColor("#e8f0fb")
C_BORDER = colors.HexColor("#b5d4f4")
C_BODY = colors.HexColor("#1a1a2e")
C_CAPTION = colors.HexColor("#555555")

C_GOOD = colors.HexColor("#1a7a4a")
C_WARN = colors.HexColor("#b36b00")
C_BAD = colors.HexColor("#a32d2d")
C_NEUTRAL = colors.HexColor("#5f5e5a")

#: Verdict -> colour. Keys match the GUI's classify_report output.
#:
#: No glyphs: Helvetica has no ✓/⚠/✕/●, and ReportLab silently substitutes a
#: tofu box for each, which reads as a design element rather than the missing
#: character it is. Colour plus the word carries the verdict on its own.
_VERDICT_STYLE: dict[str, colors.Color] = {
    "Good to Go": C_GOOD,
    "Minor Issue": C_WARN,
    "Needs Manual Review": C_NEUTRAL,
    "Need TAAP": C_BAD,
    "Deny": C_BAD,
}

_STATUS_COLOR: dict[str, colors.Color] = {
    "Supports": C_GOOD,
    "Partially Supports": C_WARN,
    "Does Not Support": C_BAD,
    "Not Applicable": C_NEUTRAL,
    "Not Evaluated": C_NEUTRAL,
}

#: Reviewer answer -> the phrasing the sheet prints. Wording tracks the full
#: renderer's Impact Assessment table (and the GUI's own button labels) on
#: purpose: the two reports are read side by side, and the same choice reading
#: two ways looks like two different answers.
#:
#: An unrecognized value is humanized, never dropped -- see ``_answer``.
_AUDIENCE_LABEL: dict[str, str] = {
    "individual": "1 user (individual)",
    "small_team": "2–20 users (small team)",
    "campus_wide": "21+ users (campus-wide)",
}
_ACCESS_LABEL: dict[str, str] = {
    "no_limit": "Does not limit access",
    "limits_some": "Limits some access",
    "denies_access": "Denies access to features",
}
_LEGAL_LABEL: dict[str, str] = {
    "low": "Low legal exposure",
    "medium": "Medium legal exposure",
    "high": "High legal exposure",
}
_DEPLOY_LABEL: dict[str, str] = {
    "individual": "Individual deployment",
    "department": "Department deployment",
    "campus_wide": "Campus-wide deployment",
}

#: Progressively tighter budgets: (max barriers, summary chars, recommendation
#: chars, font size). Level 0 is the intended look; the rest are fallbacks for
#: documents with long criterion titles or a verbose AI recommendation.
#:
#: **Trim text before type.** The levels drop characters faster than points, and
#: the floor is 9pt: this is an accessibility report, and a legible sheet that
#: says less beats a complete one nobody can read. 9pt is also where the ladder
#: used to *start* -- the worst case here is the old intended look.
_TRIM_LEVELS: list[tuple[int, int, int, float]] = [
    (5, 460, 420, 11.0),
    (5, 340, 300, 10.5),
    (4, 260, 240, 10.0),
    (3, 190, 180, 9.5),
    (2, 130, 120, 9.0),
]

MARGIN = 0.55 * inch
CONTENT_W = letter[0] - 2 * MARGIN


def _esc(text: object) -> str:
    """Escape document-supplied text; see reportlab_renderer._esc for the why."""
    from xml.sax.saxutils import escape

    return escape("" if text is None else str(text))


def _clip(text: str, limit: int) -> str:
    """Trim to a budget on a word boundary, marking that something was cut."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _answer(answers: dict[str, str], key: str, labels: dict[str, str]) -> str:
    """One reviewer choice, phrased for print.

    An unknown value is humanized rather than dropped: the answer drove the
    impact level either way, so hiding it would leave the sheet claiming a
    rating it does not show the basis for.
    """
    raw = (answers or {}).get(key, "")
    if not raw:
        return ""
    return labels.get(raw, raw.replace("_", " "))


def _short_status(status: str) -> str:
    """Fit a status into a narrow column without losing which one it is."""
    return {
        "Partially Supports": "Partial",
        "Does Not Support": "Does Not",
        "Not Applicable": "N/A",
        "Not Evaluated": "Not Eval",
    }.get(status, status)


class OnePageRenderer:
    """Renders the single-page decision sheet. Satisfies the ReportRenderer port."""

    output_suffix = ".pdf"

    def render(self, inputs: ReportInputs, output_path: str) -> None:
        for level in range(len(_TRIM_LEVELS)):
            buf = io.BytesIO()
            pages = self._build(inputs, buf, level)
            if pages <= 1:
                with open(output_path, "wb") as f:
                    f.write(buf.getvalue())
                return
        # Every trim level still spilled. Emit the tightest anyway rather than
        # failing the review outright -- a two-page summary beats no report --
        # but this means the budgets above need revisiting.
        buf = io.BytesIO()
        self._build(inputs, buf, len(_TRIM_LEVELS) - 1)
        with open(output_path, "wb") as f:
            f.write(buf.getvalue())

    def validate(self, output_path: str) -> tuple[bool, list[str]]:
        """Check the promise this renderer exists to keep: it is one page."""
        problems: list[str] = []
        try:
            with open(output_path, "rb") as f:
                head = f.read(5)
            if head != b"%PDF-":
                problems.append("Output is not a PDF.")
                return False, problems
        except OSError as e:
            return False, [f"Could not open report: {e}"]

        try:
            from pypdf import PdfReader

            n = len(PdfReader(output_path).pages)
            if n != 1:
                problems.append(f"One-page report has {n} pages.")
        except Exception as e:  # noqa: BLE001 - a broken PDF must not crash the app
            problems.append(f"Could not read report: {e}")
        return not problems, problems

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self, inputs: ReportInputs, buf: io.BytesIO, level: int) -> int:
        max_barriers, sum_chars, rec_chars, fs = _TRIM_LEVELS[level]
        cfg: dict[str, Any] = inputs.settings or {}
        doc_model = inputs.document
        score = inputs.score

        base = ParagraphStyle(
            "op_body", fontName="Helvetica", fontSize=fs, leading=fs + 3, textColor=C_BODY
        )
        cap = ParagraphStyle(
            "op_cap", parent=base, fontSize=fs - 1, textColor=C_CAPTION, leading=fs + 2
        )
        head = ParagraphStyle(
            "op_head",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=fs - 0.5,
            textColor=C_PRIMARY,
            spaceAfter=2,
        )

        story: list[Any] = []
        story.append(self._header(cfg, fs))
        story.append(Spacer(1, 8))
        story.append(self._identity(inputs, cfg, base, cap))
        story.append(Spacer(1, 8))
        story.append(self._verdict_block(inputs, fs))
        story.append(Spacer(1, 6))
        basis = self._impact_basis(inputs)
        if basis:
            story.append(Paragraph(basis, cap))
            story.append(Spacer(1, 3))
        story.append(Paragraph(self._counts_line(score), cap))
        story.append(Spacer(1, 9))

        story.append(Paragraph("SUMMARY", head))
        story.append(Paragraph(self._summary(inputs, cfg, sum_chars), base))
        story.append(Spacer(1, 9))

        barriers = self._barriers(doc_model, max_barriers)
        if barriers:
            total = self._barrier_total(doc_model)
            label = "TOP BARRIERS"
            if total > len(barriers):
                label += f" — {len(barriers)} of {total} shown"
            story.append(KeepTogether([Paragraph(label, head), self._barrier_table(barriers, fs)]))
            story.append(Spacer(1, 9))

        story.append(Paragraph("RECOMMENDATION", head))
        story.append(Paragraph(self._recommendation(inputs, rec_chars), base))
        story.append(Spacer(1, 10))
        story.append(Paragraph(self._footer_note(cfg), cap))

        pdf = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            title=f"{doc_model.product_name or 'VPAT'} — Compliance Summary",
            author=str(cfg.get("org_name", "")),
        )
        pdf.build(story)
        return int(pdf.page)

    def _header(self, cfg: dict[str, Any], fs: float) -> Table:
        org = str(cfg.get("org_short") or "SFBRN")
        title = str(cfg.get("report_title") or "VPAT Accessibility Compliance — Summary")
        left = ParagraphStyle(
            "op_hl",
            fontName="Helvetica-Bold",
            fontSize=fs + 5,
            textColor=colors.white,
            alignment=TA_LEFT,
        )
        right = ParagraphStyle(
            "op_hr",
            fontName="Helvetica",
            fontSize=fs + 0.5,
            textColor=colors.white,
            alignment=TA_CENTER,
        )
        t = Table(
            [[Paragraph(_esc(org), left), Paragraph(_esc(title), right)]],
            colWidths=[1.3 * inch, CONTENT_W - 1.3 * inch],
        )
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), C_PRIMARY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (0, 0), 12),
                    ("RIGHTPADDING", (1, 0), (1, 0), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ]
            )
        )
        return t

    def _identity(
        self, inputs: ReportInputs, cfg: dict[str, Any], base: ParagraphStyle, cap: ParagraphStyle
    ) -> Table:
        from datetime import date

        d = inputs.document
        bits = [_esc(d.product_name or "[Product name not found]")]
        if d.vendor_name:
            bits.append(_esc(d.vendor_name))
        if d.product_version:
            bits.append("v" + _esc(d.product_version))
        line = "  ·  ".join(f"<b>{bits[0]}</b>" if i == 0 else b for i, b in enumerate(bits))

        reviewer = _esc(cfg.get("reviewer_name") or "")
        sub = f"Reviewed {date.today():%B %d, %Y}"
        if reviewer:
            sub += f" by {reviewer}"
        if d.vendor_report_date_raw:
            sub += f"  ·  Vendor VPAT dated {_esc(d.vendor_report_date_raw)}"

        t = Table([[Paragraph(line, base)], [Paragraph(sub, cap)]], colWidths=[CONTENT_W])
        t.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        return t

    def _verdict_block(self, inputs: ReportInputs, fs: float) -> Table:
        score = inputs.score.get("score")
        score_str = f"{score}%" if score is not None else "N/A"
        verdict = inputs.verdict or "—"
        vcolor = _VERDICT_STYLE.get(verdict, C_NEUTRAL)
        impact = str(inputs.impact.get("final_level") or inputs.impact.get("suggested_level") or "")

        big = ParagraphStyle(
            "op_score",
            fontName="Helvetica-Bold",
            fontSize=fs + 13,
            leading=fs + 15,
            textColor=C_PRIMARY,
            alignment=TA_CENTER,
        )
        small = ParagraphStyle(
            "op_scorecap",
            fontName="Helvetica",
            fontSize=fs - 1.5,
            textColor=C_CAPTION,
            alignment=TA_CENTER,
        )
        vstyle = ParagraphStyle(
            "op_verdict", fontName="Helvetica-Bold", fontSize=fs + 4, textColor=vcolor
        )
        istyle = ParagraphStyle("op_impact", fontName="Helvetica", fontSize=fs, textColor=C_BODY)

        score_cell = [Paragraph(score_str, big), Paragraph("COMPLIANCE SCORE", small)]
        right_cell = [
            Paragraph(_esc(verdict).upper(), vstyle),
            Spacer(1, 3),
            Paragraph(f"Impact level: <b>{_esc(impact) or '—'}</b>", istyle),
        ]
        t = Table([[score_cell, right_cell]], colWidths=[1.7 * inch, CONTENT_W - 1.7 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), C_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
                    ("LINEAFTER", (0, 0), (0, 0), 0.5, C_BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ]
            )
        )
        return t

    def _counts_line(self, score: dict[str, Any]) -> str:
        sup = score.get("supported", 0)
        total = score.get("total", 0)
        na = score.get("na_excluded", 0)
        reviewable = max(int(total) - int(sup), 0)
        parts = [
            f"<b>{sup}</b> supported",
            f"<b>{reviewable}</b> needing review",
            f"<b>{na}</b> not applicable (excluded from score)",
        ]
        return "  ·  ".join(parts)

    def _barrier_total(self, document: Any) -> int:
        return len(
            [
                c
                for c in document.criteria
                if c.level == "AA" and c.normalized_status not in ("Supports", "Not Applicable")
            ]
        )

    def _barriers(self, document: Any, limit: int) -> list[Any]:
        """Worst-first: Does Not Support before Partially Supports before the rest."""
        rank = {"Does Not Support": 0, "Not Evaluated": 1, "Partially Supports": 2}
        rows = [
            c
            for c in document.criteria
            if c.level == "AA" and c.normalized_status not in ("Supports", "Not Applicable")
        ]
        rows.sort(key=lambda c: (rank.get(c.normalized_status, 3), _sort_key(c.criterion_id)))
        return rows[:limit]

    def _barrier_table(self, barriers: list[Any], fs: float) -> Table:
        cell = ParagraphStyle("op_bcell", fontName="Helvetica", fontSize=fs - 0.5, textColor=C_BODY)
        rows: list[list[Any]] = []
        for c in barriers:
            status = c.normalized_status
            st = ParagraphStyle(
                f"op_bst_{c.criterion_id}",
                fontName="Helvetica-Bold",
                fontSize=fs - 1,
                textColor=_STATUS_COLOR.get(status, C_NEUTRAL),
            )
            title = _esc(c.title or "")
            rows.append(
                [
                    Paragraph(f"<b>{_esc(c.criterion_id)}</b>  {title}", cell),
                    Paragraph(_esc(_short_status(status)), st),
                ]
            )
        t = Table(rows, colWidths=[CONTENT_W - 1.15 * inch, 1.15 * inch])
        t.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.25, C_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    def _impact_basis(self, inputs: ReportInputs) -> str:
        """The four reviewer answers behind the impact level shown above.

        The level alone is unchallengeable: impact outranks the score in
        ``classify_report`` (High never beats Need TAAP), and it comes from
        reviewer judgment, not the document. Printing the level without its
        inputs asks the reader to trust a verdict whose basis is off-page.

        An explicit override is called out rather than shown as if it were the
        computed rating -- a reviewer's decision is theirs to own on the sheet.
        """
        a = inputs.answers or {}
        bits = [
            _answer(a, "audience", _AUDIENCE_LABEL),
            _answer(a, "access_impact", _ACCESS_LABEL),
            _answer(a, "legal_exposure", _LEGAL_LABEL),
            _answer(a, "deployment", _DEPLOY_LABEL),
        ]
        line = "  ·  ".join(_esc(b) for b in bits if b)
        if not line:
            return ""

        text = f"<b>Impact basis:</b>  {line}"
        suggested = str(inputs.impact.get("suggested_level") or "")
        final = str(inputs.impact.get("final_level") or "")
        if final and suggested and final != suggested:
            text += (
                f"  ·  set to <b>{_esc(final)}</b> by the reviewer (suggested {_esc(suggested)})"
            )
        return text

    def _summary(self, inputs: ReportInputs, cfg: dict[str, Any], limit: int) -> str:
        """The written read of the numbers above it — findings, never an action.

        Deterministic: it says what the document and the score already say, so
        the sheet still reads as a summary when Bedrock is off or unreachable.
        The action belongs under RECOMMENDATION; keep the two from converging.

        Ordered worst-news-first within the budget, because ``_clip`` truncates
        the tail: the score and the barrier count survive every trim level, the
        outdated-VPAT note is the first thing spent.
        """
        d = inputs.document
        score = inputs.score
        org = str(cfg.get("org_short") or "SFBRN")
        product = d.product_name or "the product"

        parts = [
            f"{org} reviewed the vendor-submitted VPAT for {product} against WCAG 2.1 Level AA."
        ]

        pct = score.get("score")
        supported = int(score.get("supported", 0) or 0)
        reviewable = max(int(score.get("total", 0) or 0) - supported, 0)
        if pct is None:
            parts.append(
                "The document yielded no scorable Level AA criteria, so no score is claimed."
            )
        else:
            threshold = _threshold(cfg)
            verb = "meeting" if int(pct) >= threshold else "below"
            parts.append(
                f"{supported} of {supported + reviewable} reviewable criteria are fully "
                f"supported — a compliance score of {pct}%, {verb} the {org} "
                f"{threshold}% threshold."
            )

        total_barriers = self._barrier_total(d)
        if total_barriers:
            parts.append(
                f"{total_barriers} Level AA barrier(s) were identified; the most severe "
                f"are listed below."
            )
        else:
            parts.append("No Level AA barriers were identified.")

        na = int(score.get("na_excluded", 0) or 0)
        if na:
            parts.append(f"{na} criteria were reported Not Applicable and excluded from the score.")
        if d.is_outdated:
            parts.append(
                "The vendor report is more than 12 months older than this review, so the claims "
                "may not reflect the current product; request an updated VPAT."
            )
        return _esc(_clip(" ".join(parts), limit))

    def _recommendation(self, inputs: ReportInputs, limit: int) -> str:
        """What the reader should do next -- an action, never a finding.

        Precedence matters: the impact rationale is a *reason* ("limits access
        for some users"), and printing that under a RECOMMENDATION heading tells
        a decision-maker nothing about what to do. So an explicit recommendation
        wins, then the verdict's standing action, and the rationale is only a
        last resort for an unrecognized verdict.
        """
        text = inputs.recommendation.strip()
        if not text:
            text = _DEFAULT_RECOMMENDATION.get(inputs.verdict, "")
        if not text:
            rationale = inputs.impact.get("rationale") or []
            if isinstance(rationale, list) and rationale:
                text = str(rationale[0])
        if not text:
            text = "Review the full report before making a procurement decision."
        return _esc(_clip(text, limit))

    def _footer_note(self, cfg: dict[str, Any]) -> str:
        org = _esc(cfg.get("org_short") or "SFBRN")
        return (
            f"This one-page summary condenses the full {org} review. It restates vendor "
            f"conformance claims and is not an independent audit. Per-criterion vendor remarks, "
            f"the WCAG rollup, and Section 508 results appear in the full report."
        )


_DEFAULT_RECOMMENDATION: dict[str, str] = {
    "Good to Go": "Meets the accessibility bar. Approve for deployment as-is.",
    "Minor Issue": (
        "Approve with conditions: request a vendor remediation timeline for the "
        "barriers listed above."
    ),
    "Needs Manual Review": (
        "Do not decide on the VPAT alone. Manual testing is required before approval."
    ),
    "Need TAAP": ("Escalate for a Temporary Alternative Access Plan before approval."),
    "Deny": "Do not deploy. Barriers block access to required functionality.",
}


def _threshold(cfg: dict[str, Any]) -> int:
    """The settings threshold, or the documented default if it is unusable.

    Mirrors reportlab_renderer's coercion: a hand-edited settings.json is the
    normal case here, so a string or a typo must not take the report down.
    """
    try:
        return int(cfg.get("threshold", 90))
    except (TypeError, ValueError):
        return 90


def _sort_key(criterion_id: str) -> tuple[int, ...]:
    """Numeric sort so 1.4.10 follows 1.4.9 instead of 1.4.1."""
    try:
        return tuple(int(p) for p in criterion_id.split("."))
    except ValueError:
        return (999,)
