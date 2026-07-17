"""Build the model-selection PDF: why Nova 2 Lite, and what it costs.

Dev-only. Reads the frozen eval in docs/model_eval plus the measured runs, and
renders the case for the default model -- including where that model *loses*,
because a selection document that only lists wins is marketing, not evidence.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

C_NAVY = colors.HexColor("#16324f")
C_BLUE = colors.HexColor("#2563eb")
C_BG = colors.HexColor("#f1f5fb")
C_BORDER = colors.HexColor("#cbd5e1")
C_GOOD = colors.HexColor("#15803d")
C_BAD = colors.HexColor("#b91c1c")
C_MUTE = colors.HexColor("#64748b")
C_HILITE = colors.HexColor("#eaf1ff")

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, textColor=C_NAVY, spaceAfter=3)
H2 = ParagraphStyle(
    "h2", fontName="Helvetica-Bold", fontSize=12, textColor=C_BLUE, spaceBefore=12, spaceAfter=5
)
BODY = ParagraphStyle(
    "b", fontName="Helvetica", fontSize=9, leading=12.5, textColor=colors.HexColor("#1a1a2e")
)
CELL = ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=10)
CELLB = ParagraphStyle("cb", parent=CELL, fontName="Helvetica-Bold")
CAP = ParagraphStyle("cap", fontName="Helvetica", fontSize=7.8, textColor=C_MUTE, leading=10.5)

NOVA = "Nova 2 Lite"


def load_models() -> list[dict]:
    rows = []
    md = Path("docs/model_eval/MULTIDOC_COMPARISON.md").read_text(encoding="utf-8")
    for line in md.splitlines():
        m = re.match(
            r"\|\s*\*{0,2}(.+?)\*{0,2}\s*\|\s*([\w\s]+?)\s*\|\s*(\d)/5\s*\|\s*([\d.]+)\s*\|"
            r"\s*(\d+)%\s*\|\s*\$([\d.]+)\s*\|\s*([\d.]+)s\s*\|",
            line,
        )
        if m:
            n, p, ok, q, ag, c, lat = m.groups()
            rows.append(
                {
                    "name": n.strip(),
                    "prov": p.strip(),
                    "q": float(q),
                    "ag": int(ag),
                    "cost": float(c),
                    "lat": float(lat),
                }
            )
    return rows


def _tbl(data, widths, hi_rows=()):
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_BG),
        ("GRID", (0, 0), (-1, -1), 0.25, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for r in hi_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), C_HILITE))
    t.setStyle(TableStyle(style))
    return t


def build(out_path: str) -> None:
    rows = load_models()
    nova = next(r for r in rows if r["name"] == NOVA)
    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="VPAT Reviewer — Model Selection & Cost",
    )
    S: list = []

    S.append(Paragraph("Model Selection &amp; Cost", H1))
    S.append(
        Paragraph(
            f"Which Bedrock model should decide the verdict — and what it costs. "
            f"Based on the frozen 59-model / 5-VPAT evaluation in <b>docs/model_eval</b> "
            f"(295 runs) plus measured runs. Generated {date.today():%B %d, %Y}.",
            CAP,
        )
    )
    S.append(Spacer(1, 10))

    # 1. Top 10 by quality
    S.append(Paragraph("1 · Top 10 of 56 models, ranked by quality", H2))
    data = [
        [
            Paragraph(f"<b>{h}</b>", CELL)
            for h in [
                "#",
                "Model",
                "Provider",
                "Quality",
                "Agreement",
                "Cost / doc",
                "Latency",
                "× Nova cost",
            ]
        ]
    ]
    top10 = sorted(rows, key=lambda r: -r["q"])[:10]
    hi = []
    for i, r in enumerate(top10, 1):
        data.append(
            [
                Paragraph(str(i), CELL),
                Paragraph(r["name"], CELL),
                Paragraph(r["prov"], CELL),
                Paragraph(f"<b>{r['q']}</b>", CELL),
                Paragraph(f"{r['ag']}%", CELL),
                Paragraph(f"${r['cost']:.5f}", CELL),
                Paragraph(f"{r['lat']}s", CELL),
                Paragraph(f"{r['cost'] / nova['cost']:.0f}×", CELL),
            ]
        )
    # Nova sits at #11 — show it directly beneath rather than pretend it is in the top 10.
    data.append(
        [
            Paragraph("<b>11</b>", CELLB),
            Paragraph(f"<b>{NOVA}</b>", CELLB),
            Paragraph("<b>Amazon</b>", CELLB),
            Paragraph(f"<b>{nova['q']}</b>", CELLB),
            Paragraph(f"<b>{nova['ag']}%</b>", CELLB),
            Paragraph(f"<b>${nova['cost']:.5f}</b>", CELLB),
            Paragraph(f"<b>{nova['lat']}s</b>", CELLB),
            Paragraph("<b>1×</b>", CELLB),
        ]
    )
    hi.append(len(data) - 1)
    S.append(
        _tbl(
            data,
            [
                0.3 * inch,
                1.5 * inch,
                0.85 * inch,
                0.7 * inch,
                0.85 * inch,
                0.85 * inch,
                0.7 * inch,
                0.85 * inch,
            ],
            hi,
        )
    )
    S.append(Spacer(1, 5))
    S.append(
        Paragraph(
            "<b>Nova 2 Lite is #11 by quality — it is not in the top 10, and this table does not "
            "pretend"
            "otherwise.</b> Read on for why it is still the right default: the top 10 are ranked "
            "on quality"
            "alone, which is only one of the three things that matter.",
            CAP,
        )
    )

    # 2. Where Nova actually ranks
    S.append(Paragraph("2 · Where Nova 2 Lite ranks on each axis, out of 56", H2))
    axes = [
        ("Quality", "q", True),
        ("Consensus agreement", "ag", True),
        ("Cost", "cost", False),
        ("Latency", "lat", False),
    ]
    d2 = [
        [
            Paragraph(f"<b>{h}</b>", CELL)
            for h in ["Axis", "Nova 2 Lite rank", "Nova value", "Best model", "Best value"]
        ]
    ]
    for label, key, rev in axes:
        order = sorted(rows, key=lambda r: r[key], reverse=rev)
        rank = [r["name"] for r in order].index(NOVA) + 1
        best = order[0]
        fmt = (
            (lambda x: f"${x:.5f}")
            if key == "cost"
            else (lambda x: f"{x}s")
            if key == "lat"
            else (lambda x: f"{x}%")
            if key == "ag"
            else (lambda x: f"{x}")
        )
        good = rank <= 5
        color = (C_GOOD if good else C_BAD).hexval()
        d2.append(
            [
                Paragraph(label, CELL),
                Paragraph(f'<font color="{color}"><b>#{rank}</b></font> of 56', CELL),
                Paragraph(fmt(nova[key]), CELL),
                Paragraph(best["name"], CELL),
                Paragraph(fmt(best[key]), CELL),
            ]
        )
    S.append(_tbl(d2, [1.5 * inch, 1.2 * inch, 1.0 * inch, 1.6 * inch, 1.0 * inch]))
    S.append(Spacer(1, 5))
    S.append(
        Paragraph(
            "<b>Nova 2 Lite is best at nothing on its own.</b> Sonnet 4.5 is more accurate, Nova "
            "Micro is"
            "cheaper, Llama 4 Maverick is faster, Palmyra X5 edges it on agreement. The case for "
            "it is the"
            "combination — which is what the next two tables measure.",
            CAP,
        )
    )

    S.append(PageBreak())

    # 3. Reliability bar
    S.append(
        Paragraph("3 · The reliability bar: models that matched consensus on all 5 documents", H2)
    )
    S.append(
        Paragraph(
            "Quality is a graded score for the write-up. <b>Agreement is whether the model reached "
            "the same"
            "verdict as the other 55.</b> For a procurement decision, agreement is the one that "
            "matters — a"
            "beautifully-argued wrong verdict is worse than a terse right one. Six models went "
            "5-for-5:",
            BODY,
        )
    )
    S.append(Spacer(1, 5))
    perfect = sorted([r for r in rows if r["ag"] == 100], key=lambda r: -r["q"])
    d3 = [
        [
            Paragraph(f"<b>{h}</b>", CELL)
            for h in ["Model", "Quality", "Cost / doc", "Latency", "× Nova cost"]
        ]
    ]
    hi3 = []
    for r in perfect:
        is_nova = r["name"] == NOVA
        st = CELLB if is_nova else CELL
        d3.append(
            [
                Paragraph(f"<b>{r['name']}</b>" if is_nova else r["name"], st),
                Paragraph(str(r["q"]), st),
                Paragraph(f"${r['cost']:.5f}", st),
                Paragraph(f"{r['lat']}s", st),
                Paragraph(f"{r['cost'] / nova['cost']:.1f}×", st),
            ]
        )
        if is_nova:
            hi3.append(len(d3) - 1)
    S.append(_tbl(d3, [1.9 * inch, 0.9 * inch, 1.0 * inch, 0.9 * inch, 1.0 * inch], hi3))
    S.append(Spacer(1, 5))
    S.append(
        Paragraph(
            "<b>This is the whole argument.</b> Only Palmyra X5 scores higher than Nova 2 Lite "
            "here — by"
            "<b>0.3 quality points</b> — and it costs <b>47× more</b> and takes 2.5× longer. Every "
            "other"
            "perfect-agreement model is both worse and dearer. Nova 2 Lite is the cheapest model "
            "on this"
            "list by a factor of three, and near the top of it.",
            CAP,
        )
    )

    # 4. Pareto
    S.append(Paragraph("4 · Pareto frontier — nothing beats these on both quality and cost", H2))
    front = [
        r
        for r in rows
        if not any(
            o["q"] >= r["q"]
            and o["cost"] <= r["cost"]
            and o is not r
            and (o["q"] > r["q"] or o["cost"] < r["cost"])
            for o in rows
        )
    ]
    d4 = [
        [
            Paragraph(f"<b>{h}</b>", CELL)
            for h in ["Model", "Quality", "Agreement", "Cost / doc", "Latency", "Verdict"]
        ]
    ]
    hi4 = []
    notes = {
        "Nova Micro": "Cheaper, but 65.3 quality and misses consensus 2 of 5",
        NOVA: "Only frontier model with 100% agreement — the pick",
        "MiniMax M2.1": "+0.7 quality for 7× the cost",
        "Kimi K2.5": "+4.6 quality for 12× the cost",
        "Claude Sonnet 4.5": "+9.2 quality for 89× the cost and 8× the latency",
    }
    for r in sorted(front, key=lambda r: r["cost"]):
        is_nova = r["name"] == NOVA
        st = CELLB if is_nova else CELL
        d4.append(
            [
                Paragraph(f"<b>{r['name']}</b>" if is_nova else r["name"], st),
                Paragraph(str(r["q"]), st),
                Paragraph(f"{r['ag']}%", st),
                Paragraph(f"${r['cost']:.5f}", st),
                Paragraph(f"{r['lat']}s", st),
                Paragraph(notes.get(r["name"], ""), st),
            ]
        )
        if is_nova:
            hi4.append(len(d4) - 1)
    S.append(
        _tbl(d4, [1.25 * inch, 0.6 * inch, 0.75 * inch, 0.8 * inch, 0.6 * inch, 3.3 * inch], hi4)
    )
    S.append(Spacer(1, 5))
    S.append(
        Paragraph(
            "Five of 56 models are undominated. <b>Nova 2 Lite is the only one of them that also "
            "agreed with"
            "consensus on every document.</b> That is the defensible claim — not that it is the "
            "best model,"
            "but that nothing cheaper is as good and nothing better is close to as cheap.",
            CAP,
        )
    )

    S.append(PageBreak())

    # 5. Cost
    S.append(Paragraph("5 · What it costs to run", H2))
    d5 = [[Paragraph(f"<b>{h}</b>", CELL) for h in ["Workload", "Tokens in", "Tokens out", "Cost"]]]
    per_in, per_out = 13_230, 501  # measured, Google Docs VPAT
    rate_in, rate_out = 0.06e-6, 0.23e-6  # $/token, derived from the eval's own figures

    def money(i, o):
        return f"${i * rate_in + o * rate_out:.4f}"

    for label, mult in [
        ("One VPAT review", 1),
        ("The 17-document corpus", 17),
        ("100 reviews", 100),
        ("1,000 reviews", 1000),
        ("10,000 reviews", 10000),
    ]:
        i, o = per_in * mult, per_out * mult
        d5.append(
            [
                Paragraph(label, CELL),
                Paragraph(f"{i:,}", CELL),
                Paragraph(f"{o:,}", CELL),
                Paragraph(f"<b>{money(i, o)}</b>", CELL),
            ]
        )
    S.append(_tbl(d5, [2.0 * inch, 1.3 * inch, 1.3 * inch, 1.1 * inch]))
    S.append(Spacer(1, 5))
    S.append(
        Paragraph(
            "A review sends the parsed VPAT (~13,200 tokens) and gets ~500 back. At Nova 2 Lite's "
            "rate —"
            "$0.06/M input, $0.23/M output — that is <b>~$0.001 per review</b>, or about "
            "<b>1,270 reviews per dollar</b>. The same 1,000 reviews on Claude Sonnet 4.5 would "
            "cost ~$59,"
            "and on Opus 4.6 ~$119.",
            CAP,
        )
    )
    S.append(Spacer(1, 8))

    S.append(Paragraph("6 · Honest caveats", H2))
    S.append(
        Paragraph(
            "<b>The quality and agreement figures predate the current rubric.</b> The evaluation "
            "was run"
            "against an earlier version of <b>ai/data/risk_review_prompt.md</b>, and models are "
            "graded against"
            "the rubric. Re-run the evaluation before treating these numbers as current — a "
            "measured 5-document"
            "re-run showed all three tested models shifting under the new rules.<br/><br/>"
            "<b>Nova 2 Lite is the lenient one.</b> Measured against the offline rules across the "
            "17-document"
            "corpus, it returned Good to Go for documents with open barriers, and it never "
            "returned Deny — not"
            "once, including a 45% document. Under-stating risk is the dangerous direction for a "
            "procurement"
            "verdict. That is the price of the 5 seconds and the tenth of a cent.<br/><br/>"
            "<b>This is why the human stays in the loop.</b> <b>needs_human_review</b> defaults to "
            "true, the"
            "audit log stamps <b>verdict_source</b> on every row so an AI verdict is never "
            "mistaken for a"
            "deterministic one, and a failed or unreadable model answer falls back to the offline "
            "rules rather"
            "than guessing.",
            BODY,
        )
    )
    doc.build(S)


if __name__ == "__main__":
    out = "VPAT_Model_Selection.pdf"
    build(out)
    print("wrote", out)
