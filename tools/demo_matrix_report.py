"""Build the demo playbook PDF from demo_matrix.json.

Dev-only, like the rest of tools/: it answers "which document and which answers
demonstrate verdict X?", which is a question about a demo, not about a review.

Run tools/demo_matrix.py-style collection first (see the README section this
prints), then this to render.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
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
C_WARN = colors.HexColor("#b45309")
C_BAD = colors.HexColor("#b91c1c")
C_MUTE = colors.HexColor("#64748b")

VERDICT_COLOR = {
    "Good to Go": C_GOOD,
    "Minor Issue": colors.HexColor("#4d7c0f"),
    "Needs Manual Review": C_WARN,
    "Need TAAP": colors.HexColor("#c2410c"),
    "Deny": C_BAD,
}

S_H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, textColor=C_NAVY, spaceAfter=4)
S_H2 = ParagraphStyle(
    "h2", fontName="Helvetica-Bold", fontSize=11.5, textColor=C_BLUE, spaceBefore=10, spaceAfter=5
)
S_BODY = ParagraphStyle(
    "b", fontName="Helvetica", fontSize=8.6, leading=11.5, textColor=colors.HexColor("#1a1a2e")
)
S_CELL = ParagraphStyle(
    "c", fontName="Helvetica", fontSize=7.4, leading=9, textColor=colors.HexColor("#1a1a2e")
)
S_CELLB = ParagraphStyle("cb", parent=S_CELL, fontName="Helvetica-Bold")
S_CAP = ParagraphStyle("cap", fontName="Helvetica", fontSize=7.6, textColor=C_MUTE, leading=10)

SCEN_LABEL = {
    "Individual": "1 user · Does not limit · Low · Individual",
    "Department": "2–20 users · Limits some · Low · Department",
    "Campus": "21+ users · Limits some · Medium · Campus-wide",
    "Campus+Denies": "21+ users · Denies access · High · Campus-wide",
}


def short(name: str, n: int = 30) -> str:
    return (
        name[:-4]
        if name.lower().endswith((".pdf", ".doc"))
        else name[:-5]
        if name.lower().endswith(".docx")
        else name
    )


def v(text: str) -> Paragraph:
    """A verdict cell, coloured by verdict."""
    c = VERDICT_COLOR.get(text, C_MUTE)
    return Paragraph(f'<font color="{c.hexval()}">{text}</font>', S_CELL)


def build(rows: list[dict], out_path: str) -> None:
    doc = SimpleDocTemplate(
        out_path,
        pagesize=landscape(letter),
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title="VPAT Reviewer — Demo Playbook & Model Comparison",
    )
    story: list = []

    story.append(Paragraph("VPAT Reviewer — Demo Playbook &amp; Model Comparison", S_H1))
    story.append(
        Paragraph(
            f"17 vendor documents · AI = Amazon Nova 2 Lite (us.amazon.nova-2-lite-v1:0) · "
            f"Offline = domain/verdict.py rules · Generated {date.today():%B %d, %Y}",
            S_CAP,
        )
    )
    story.append(Spacer(1, 10))

    # ── The one thing that decides how you demo ──────────────────────────────
    story.append(
        Paragraph("Read this first: the four questions do not change the AI verdict", S_H2)
    )
    story.append(
        Paragraph(
            "With <b>use_ai: true</b> (the shipped default) the category comes from the model "
            "reading the"
            "document. The four Impact Assessment answers feed the <i>impact level</i> and the "
            "report — they do"
            "not change the AI's category. They only decide the verdict when the app runs "
            "<b>offline</b>"
            "(<b>use_ai: false</b>, or whenever Bedrock is unreachable).<br/><br/>"
            "So: <b>to demo by document, leave AI on. To demo the questions changing the outcome, "
            "turn AI off.</b>"
            "Both are real product behaviour; the panel tells you which decided.",
            S_BODY,
        )
    )
    story.append(Spacer(1, 8))

    # ── Table 1: the full comparison ─────────────────────────────────────────
    story.append(Paragraph("1 · All 17 documents — offline rules vs Nova 2 Lite", S_H2))
    head = [
        "Document",
        "Kind",
        "Score",
        "Barr",
        "Offline\n(Individual)",
        "Offline\n(Department)",
        "Offline\n(Campus)",
        "Offline\n(Campus+Denies)",
        "Nova 2 Lite\n(AI)",
        "Agree?",
        "Sec",
    ]
    data = [[Paragraph(f"<b>{h}</b>", S_CELL) for h in head]]
    agree_n = total_n = 0
    for r in rows:
        ai = r.get("ai")
        if ai is None:
            ai_cell, agree = Paragraph("<i>not sent</i>", S_CELL), Paragraph("—", S_CELL)
        else:
            ai_cell = v(ai)
            same = ai == r["off_Department"]
            color = (C_GOOD if same else C_BAD).hexval()
            txt = "yes" if same else "NO"
            agree = Paragraph(f'<font color="{color}">{txt}</font>', S_CELLB)
            agree_n += same
            total_n += 1
        data.append(
            [
                Paragraph(short(r["doc"]), S_CELL),
                Paragraph(r["kind"].replace("_", " "), S_CELL),
                Paragraph("—" if r["score"] is None else f"<b>{r['score']}%</b>", S_CELL),
                Paragraph(str(r["barriers"]), S_CELL),
                v(r["off_Individual"]),
                v(r["off_Department"]),
                v(r["off_Campus"]),
                v(r["off_Campus+Denies"]),
                ai_cell,
                agree,
                Paragraph("—" if r.get("secs") is None else str(r["secs"]), S_CELL),
            ]
        )
    widths = [
        1.95 * inch,
        0.72 * inch,
        0.42 * inch,
        0.34 * inch,
        1.05 * inch,
        1.05 * inch,
        1.05 * inch,
        1.05 * inch,
        1.05 * inch,
        0.42 * inch,
        0.32 * inch,
    ]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_BG),
                ("GRID", (0, 0), (-1, -1), 0.25, C_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 5))
    story.append(
        Paragraph(
            f"“Agree?” compares Nova against the offline rules in the <b>Department</b> "
            f"scenario. Agreement: <b>{agree_n}/{total_n}</b>. Four documents are not VPATs "
            f"— the parser refuses them and nothing is sent to AWS, which is the correct "
            f"behaviour, not a failure.",
            S_CAP,
        )
    )

    story.append(PageBreak())

    # ── Table 2: the demo playbook ───────────────────────────────────────────
    story.append(Paragraph("2 · Demo playbook — two documents per verdict", S_H2))
    story.append(
        Paragraph(
            "Each row is a demo you can run as-is. “Mode” matters: rows marked <b>offline</b> need "
            "<b>use_ai: false</b> in settings.json, because that verdict is produced by the rules, "
            "not the model.",
            S_BODY,
        )
    )
    story.append(Spacer(1, 6))

    head2 = [
        "Verdict to show",
        "Document",
        "Mode",
        "Answer these four questions",
        "Why it lands there",
    ]
    d2 = [[Paragraph(f"<b>{h}</b>", S_CELL) for h in head2]]

    def row(verdict, doc, mode, answers, why, first=False):
        d2.append(
            [
                Paragraph(
                    f'<font color="{VERDICT_COLOR[verdict].hexval()}"><b>{verdict}</b></font>',
                    S_CELL,
                )
                if first
                else Paragraph("", S_CELL),
                Paragraph(f"<b>{doc}</b>", S_CELL),
                Paragraph(mode, S_CELL),
                Paragraph(answers, S_CELL),
                Paragraph(why, S_CELL),
            ]
        )

    ANY = "Any answers — the model decides"
    row(
        "Good to Go",
        "Canvas VPAT_2026",
        "AI <b>or</b> offline",
        ANY + " · offline: " + SCEN_LABEL["Department"],
        "100% score, zero barriers — the only document both paths call Good to Go. The clean case.",
        first=True,
    )
    row(
        "Good to Go",
        "WRDS_January_2026",
        "AI only",
        ANY,
        "98%, 1 barrier. Nova says Good to Go; the rules say Minor Issue (they require <i>zero</i> "
        "barriers)."
        "Good for showing the two paths disagreeing.",
    )

    row(
        "Minor Issue",
        "iCIMS_August_2024",
        "AI <b>or</b> offline",
        ANY + " · offline: " + SCEN_LABEL["Department"],
        "92%, 4 barriers. Both paths agree — the safest Minor Issue demo.",
        first=True,
    )
    row(
        "Minor Issue",
        "Google_Classroom_Web",
        "AI <b>or</b> offline",
        ANY + " · offline: " + SCEN_LABEL["Department"],
        "89%, 6 barriers. Both paths agree.",
    )

    row(
        "Needs Manual Review",
        "AnatomyLT_SSU_June_2026",
        "either",
        "Not asked — the app refuses the file",
        "Not a VPAT. The app declines to score it rather than produce an authoritative-looking "
        "number."
        "The strongest safety story in the demo.",
        first=True,
    )
    row(
        "Needs Manual Review",
        "Atrium_Connect_April_2026",
        "AI only",
        ANY,
        "76%, 13 barriers. Nova asks for a human; the rules say Minor Issue.",
    )

    row(
        "Need TAAP",
        "Google_Drawings",
        "AI <b>or</b> offline",
        ANY + " · offline: " + SCEN_LABEL["Department"],
        "57%, 19 barriers. Both paths agree — the best Need TAAP demo.",
        first=True,
    )
    row(
        "Need TAAP",
        "Sample_VPAT",
        "AI <b>or</b> offline",
        ANY + " · offline: " + SCEN_LABEL["Department"],
        "69%, 11 barriers. Both paths agree.",
    )

    row(
        "Deny",
        "Google_Docs_Web",
        "<b>offline only</b>",
        SCEN_LABEL["Department"],
        "45% with barriers that block core functions → High impact and a score under 50. "
        "<b>Nova never returned Deny on any of the 17</b>, so this verdict cannot be demoed with "
        "AI on.",
        first=True,
    )
    row(
        "Deny",
        "Any VPAT",
        "<b>offline only</b>",
        SCEN_LABEL["Campus+Denies"],
        "“Denies access to features” + High impact forces Deny regardless of score — even Canvas "
        "at 100%."
        "Use this to show the questions overriding a good score.",
    )

    t2 = Table(
        d2, colWidths=[1.05 * inch, 1.55 * inch, 0.9 * inch, 2.5 * inch, 4.4 * inch], repeatRows=1
    )
    style2 = [
        ("BACKGROUND", (0, 0), (-1, 0), C_BG),
        ("GRID", (0, 0), (-1, -1), 0.25, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(d2), 2):  # band each verdict pair
        style2.append(
            ("BACKGROUND", (0, i), (-1, min(i + 1, len(d2) - 1)), colors.HexColor("#fafcff"))
        )
    t2.setStyle(TableStyle(style2))
    story.append(t2)
    story.append(Spacer(1, 10))

    # ── What the comparison says ─────────────────────────────────────────────
    story.append(Paragraph("3 · What this says about the model", S_H2))
    story.append(
        Paragraph(
            f"<b>Agreement: {agree_n} of {total_n}.</b> Where Nova and the rules differ, "
            "<b>Nova is consistently the more lenient of the two</b> — Good to Go for H5P (94%, 3 "
            "barriers),"
            "Canvas 2023 (88%, 6 barriers) and WRDS (98%, 1 barrier), all of which the rules cap "
            "at Minor Issue"
            "because Good to Go demands zero barriers. It also never returned <b>Deny</b> on any "
            "of the 17,"
            "downgrading Google Docs (45%) to Need TAAP.<br/><br/>"
            "Leniency is the unsafe direction for a procurement verdict: it under-states risk. "
            "That is the"
            "trade for ~5s and ~$0.001 per document, and it is why <b>needs_human_review</b> "
            "defaults to true and"
            "why the audit log records <b>verdict_source</b> on every row.<br/><br/>"
            "<b>Where Nova is stronger:</b> it reads the vendor's remarks, not just the "
            "arithmetic. Cornerstone"
            "(35%) is Need TAAP to Nova but Needs Manual Review to the rules in a departmental "
            "scenario — the"
            "rules only reach Deny there once the deployment is campus-wide.",
            S_BODY,
        )
    )
    doc.build(story)


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "demo_matrix.json")
    out = sys.argv[2] if len(sys.argv) > 2 else "VPAT_Demo_Playbook.pdf"
    build(json.loads(src.read_text(encoding="utf-8")), out)
    print("wrote", out)
