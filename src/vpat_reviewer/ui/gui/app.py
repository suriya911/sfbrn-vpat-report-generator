"""
SFBRN VPAT Reviewer — Desktop Application
Python + Tkinter GUI
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# GUI as an adapter: import the package directly (not the legacy root shims).
# This module is the composition root for the AI review — it is where "which
# model" is decided and where `use_ai` is honored. service.assess_result takes
# the assessor as an argument precisely so the library never reaches for a
# network on its own.
from vpat_reviewer import audit
from vpat_reviewer.ai.base import AssessmentError, RiskAssessment
from vpat_reviewer.ai.bedrock import BedrockAssessor, BedrockConfig
from vpat_reviewer.config import settings as settings_manager
from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.scoring import compliance_score
from vpat_reviewer.domain.scoring import get_barriers as get_aa_barriers
from vpat_reviewer.domain.verdict import CATEGORIES, classify_report
from vpat_reviewer.parsing import parse_vpat
from vpat_reviewer.reporting import ReportInputs, renderer_for
from vpat_reviewer.service import (
    ReviewResult,
    assess_result,
    build_assessment_request,
    build_audit_event,
    write_json,
)
from vpat_reviewer.ui.gui.policy_dialog import GradingPolicyDialog
from vpat_reviewer.ui.gui.widgets import (
    FlatButton,
    make_scrollable,
    size_scrollable_dialog,
    work_area,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Design system ────────────────────────────────────────────────────────────────
# A soft, modern palette. Old constant names are kept as aliases at the bottom so
# the rest of the file needs no churn.
BG_APP = "#eef1f7"  # app canvas
BG_CARD = "#ffffff"  # card surface
BG_HEADER = "#16324f"  # top bar
BG_SECTION = "#f1f5fb"  # inset panels
BG_PANEL = "#eef1f7"  # right summary column
BG_HOVER = "#f4f7fc"

FG_INK = "#0f172a"  # primary text
FG_NAVY = "#16324f"  # headings
FG_MUTED = "#64748b"  # captions
FG_WHITE = "#ffffff"
FG_ONACC = "#eaf1ff"  # muted text on accent

BORDER = "#e2e8f0"  # hairline borders
ACCENT = "#2563eb"  # interactive blue
ACCENT_HOV = "#1d4ed8"
ACCENT_SFT = "#eaf1ff"  # accent tint fill

C_GREEN = "#15803d"
C_ORANGE = "#b45309"
C_RED = "#b91c1c"

# Back-compat aliases (used throughout the methods below).
FG_BLUE = ACCENT
FG_BODY = FG_INK
FG_CAPTION = FG_MUTED
C_BORDER = BORDER
C_SUCCESS = C_GREEN
C_BTN_PRI = ACCENT
C_BTN_HOV = ACCENT_HOV

FONT = "Segoe UI"
IMPACT_COLORS = {"High": C_RED, "Medium": C_ORANGE, "Low": C_GREEN}

# ── Report categorization ───────────────────────────────────────────────────────
# The five verdicts live in domain/verdict.py — the rubric, the validator and this
# panel must all name them identically. Here we only add presentation: each maps to
# (accent colour, glyph, one-line meaning) for the side panel, and to an on-disk
# folder name reports are filed under.
CATEGORY_META = {
    "Good to Go": ("#15803d", "✓", "Meets the bar — ready to deploy as-is."),
    "Minor Issue": ("#4d7c0f", "◐", "Deployable, with a few small gaps to track."),
    "Needs Manual Review": ("#b45309", "?", "Inconclusive — a human reviewer must decide."),
    "Need TAAP": ("#c2410c", "!", "Gaps require a Temporary Alternative Access Plan."),
    "Deny": ("#b91c1c", "✕", "Fails the bar — do not deploy without remediation."),
}
CATEGORY_FOLDER = {
    "Good to Go": "Good To Go",
    "Minor Issue": "Minor Issue",
    "Needs Manual Review": "Needs Manual Review",
    "Need TAAP": "Need TAAP",
    "Deny": "Deny",
}


def _impact_from_risk(risk_level: str) -> str | None:
    """The report's Low/Medium/High from the rubric's risk level. None = no opinion.

    "Critical" becomes "High" because the report's scale has no cell above it and
    Critical is unambiguously inside High — lossy, but not invented, and the
    model's own word survives in the JSON sidecar either way.

    "Unknown" returns None: the model declined to rate the risk. The previous
    implementation called that "Medium", manufacturing a rating nobody gave. We
    already computed a real one deterministically, so we keep it.
    """
    if risk_level == "Critical":
        return "High"
    if risk_level in ("Low", "Medium", "High"):
        return risk_level
    return None  # "Unknown" — validation guarantees nothing else reaches here.


def _rationale_bullets(assessment) -> list[str]:
    """The report's rationale bullets, assembled from a validated assessment."""
    bullets = []
    if assessment.reason:
        bullets.append(assessment.reason)
    # Prefer the concrete risks; fall back to the generic signals.
    bullets.extend(assessment.major_accessibility_risks or assessment.signals_found)
    bullets += [f"Missing/unclear: {g}" for g in assessment.missing_or_unclear_information]
    recs = ([assessment.recommendation] if assessment.recommendation else []) + list(
        assessment.next_steps
    )
    if recs:
        bullets.append("Recommendations: " + "; ".join(recs))
    if assessment.needs_human_review:
        # The model asking for a human is the single thing a reviewer must not
        # miss, and the previous implementation discarded it along with the
        # confidence. A weak verdict still counts — but it says so.
        bullets.append(
            f"The model flagged this for human review "
            f"(confidence {assessment.confidence:.2f})."
        )
    return bullets


def _status_color(status: str) -> str:
    """Colour a conformance status for the barrier dots."""
    s = (status or "").lower()
    if "does not" in s:
        return C_RED
    if "partial" in s:
        return C_ORANGE
    if "not evaluated" in s or "not applicable" in s:
        return FG_MUTED
    if "support" in s:
        return C_GREEN
    return FG_MUTED


# ── Folder helpers ─────────────────────────────────────────────────────────────


def _desktop() -> Path:
    return Path.home() / "Desktop"


def _ensure_folders() -> tuple:
    base = _desktop() / "VPAT Reviewer Files"
    vpats = base / "VPATs"
    reports = base / "VPAT Summary Reports"
    ai_prompts = base / "AI Prompts"
    ai_responses = base / "AI Responses"
    for d in (base, vpats, reports, ai_prompts, ai_responses):
        d.mkdir(parents=True, exist_ok=True)
    return vpats, reports, ai_prompts, ai_responses


def _ensure_category_dirs(reports: Path) -> dict:
    """Create the five verdict subfolders under the reports dir; return name→Path."""
    dirs = {}
    for cat in CATEGORIES:
        d = reports / CATEGORY_FOLDER[cat]
        d.mkdir(parents=True, exist_ok=True)
        dirs[cat] = d
    return dirs


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()


def _next_report_path(reports_dir: Path, product: str) -> Path:
    today = date.today().strftime("%Y-%m-%d")
    # Truncate to 50 chars to prevent Windows MAX_PATH issues
    safe = (_safe_filename(product) or "Product")[:50].strip()
    base = f"{safe}_VPAT_Summary_Report_{today}"
    path = reports_dir / f"{base}.pdf"
    if not path.exists():
        return path
    v = 2
    while True:
        path = reports_dir / f"{base}_v{v}.pdf"
        if not path.exists():
            return path
        v += 1


# ── Settings dialog (first-run setup + Settings button) ───────────────────────


class SettingsDialog(tk.Toplevel):
    """Asks who is using the app so reports carry the right organization,
    reviewer name, contact, threshold, and logo. Shown automatically on
    first run; reachable any time via the Settings button."""

    def __init__(self, parent, first_run=False):
        super().__init__(parent)
        self.title("VPAT Reviewer — Setup" if first_run else "Settings")
        self.configure(bg=BG_CARD)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.saved = False

        current = settings_manager.load_settings()

        # Pinned footer: pack first with side="bottom" so the action buttons
        # always reserve their space and are never pushed off-screen by the
        # fields above (which now scroll on a short or scaled display).
        btn_row = tk.Frame(self, bg=BG_CARD)
        btn_row.pack(side="bottom", fill="x")
        btns = tk.Frame(btn_row, bg=BG_CARD)
        btns.pack(pady=12)
        FlatButton(
            btns,
            text="Save Settings",
            font=(FONT, 9, "bold"),
            bg=C_BTN_PRI,
            fg=FG_WHITE,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._save,
        ).pack(side="left", padx=6)
        FlatButton(
            btns,
            text="Grading Policy…",
            font=(FONT, 9),
            bg=BG_SECTION,
            fg=FG_NAVY,
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._open_grading,
        ).pack(side="left", padx=6)
        if not first_run:
            FlatButton(
                btns,
                text="Cancel",
                font=(FONT, 9),
                bg=BG_SECTION,
                fg=FG_NAVY,
                relief="flat",
                padx=16,
                pady=6,
                cursor="hand2",
                command=self.destroy,
            ).pack(side="left", padx=6)

        # Scrollable field area above the footer.
        canvas, body = make_scrollable(self, getattr(self._root(), "_canvases", set()), bg=BG_CARD)

        intro = (
            "Welcome! Answer a few questions so your reports show the "
            "right organization and reviewer. You can change these any "
            "time from the Settings button."
            if first_run
            else "Update the reviewer and organization details used on generated reports."
        )
        tk.Label(
            body,
            text=intro,
            font=(FONT, 9),
            bg=BG_CARD,
            fg=FG_CAPTION,
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 8), sticky="w")

        self._vars = {}
        row = 1
        for key, label in settings_manager.FIELD_LABELS:
            tk.Label(body, text=label + ":", font=(FONT, 9, "bold"), bg=BG_CARD, fg=FG_NAVY).grid(
                row=row, column=0, padx=(16, 6), pady=4, sticky="e"
            )
            var = tk.StringVar(value=str(current.get(key, "")))
            tk.Entry(body, textvariable=var, font=(FONT, 9), width=38).grid(
                row=row, column=1, padx=(0, 16), pady=4, sticky="w"
            )
            self._vars[key] = var
            row += 1

        # Report style. Not in FIELD_LABELS: that drives free-text entries, and
        # this is a closed choice of two renderers (see reporting.renderer_for).
        tk.Label(
            body, text="Report style:", font=(FONT, 9, "bold"), bg=BG_CARD, fg=FG_NAVY
        ).grid(row=row, column=0, padx=(16, 6), pady=4, sticky="ne")
        style_row = tk.Frame(body, bg=BG_CARD)
        style_row.grid(row=row, column=1, padx=(0, 16), pady=4, sticky="w")
        self._vars["report_style"] = tk.StringVar(
            value=str(current.get("report_style", "full") or "full")
        )
        for value, label in (
            ("full", "Full report — every criterion, vendor remarks, WCAG rollup"),
            ("one_page", "One-page summary — verdict, score, top barriers, action"),
        ):
            tk.Radiobutton(
                style_row,
                text=label,
                value=value,
                variable=self._vars["report_style"],
                font=(FONT, 8),
                bg=BG_CARD,
                fg=FG_NAVY,
                activebackground=BG_CARD,
                selectcolor=BG_CARD,
                anchor="w",
                cursor="hand2",
            ).pack(anchor="w")
        row += 1

        # Optional custom logo
        tk.Label(
            body, text="Custom logo (optional):", font=(FONT, 9, "bold"), bg=BG_CARD, fg=FG_NAVY
        ).grid(row=row, column=0, padx=(16, 6), pady=4, sticky="e")
        logo_row = tk.Frame(body, bg=BG_CARD)
        logo_row.grid(row=row, column=1, padx=(0, 16), pady=4, sticky="w")
        self._vars["logo_path"] = tk.StringVar(value=str(current.get("logo_path", "")))
        tk.Entry(logo_row, textvariable=self._vars["logo_path"], font=(FONT, 8), width=28).pack(
            side="left"
        )
        FlatButton(
            logo_row, text="Browse…", font=(FONT, 8), command=self._browse_logo, cursor="hand2"
        ).pack(side="left", padx=4)
        row += 1
        tk.Label(
            body,
            text="Leave logo blank to use the bundled default.",
            font=(FONT, 8),
            bg=BG_CARD,
            fg=FG_CAPTION,
        ).grid(row=row, column=1, padx=(0, 16), sticky="w")

        size_scrollable_dialog(self, canvas, body, btn_row)

    def _open_grading(self):
        """Open the editable grading-policy editor (score bands, thresholds, statuses)."""
        GradingPolicyDialog(self)

    def _browse_logo(self):
        path = filedialog.askopenfilename(
            title="Choose logo image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif"), ("All files", "*.*")],
        )
        if path:
            self._vars["logo_path"].set(path)

    def _save(self):
        values = {k: v.get().strip() for k, v in self._vars.items()}
        if not values.get("org_name") or not values.get("reviewer_name"):
            messagebox.showwarning(
                "Missing Information",
                "Organization name and reviewer name are required.",
                parent=self,
            )
            return
        try:
            values["threshold"] = max(0, min(100, int(values["threshold"])))
        except (TypeError, ValueError):
            values["threshold"] = 90
        if settings_manager.save_settings(values):
            self.saved = True
            self.destroy()
        else:
            messagebox.showerror(
                "Save Failed",
                "Could not write settings.json. Check folder permissions.",
                parent=self,
            )


# ── Main application ───────────────────────────────────────────────────────────


class VPATReviewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SFBRN VPAT Reviewer")
        self.configure(bg=BG_APP)
        self.resizable(True, True)

        # Match Tk's point→pixel scaling to the real monitor DPI so text is crisp
        # and correctly sized once the process is DPI-aware (see
        # _enable_dpi_awareness in main()). `tk scaling` is an absolute factor,
        # so setting it explicitly is deterministic regardless of Tk's own guess.
        dpi = self.winfo_fpixels("1i")
        self._dpi_scale = dpi / 96.0  # OS scale factor: 1.0 @100%, 1.5 @150%, …
        self.tk.call("tk", "scaling", dpi / 72.0)

        # Fit the window to the actual usable screen and set a floor that never
        # exceeds it. This is the root-cause fix for buttons being cut off: the
        # old fixed 1460×1000 / minsize 1120×740 overflowed scaled displays (and
        # a 1366×768 laptop couldn't even hold the 740px minimum at 100%).
        self._fit_to_work_area()

        # State
        self.vpat_path = tk.StringVar(value="")
        self.vpat_data = None
        self.score_info = {}
        self.impact_info = {}
        self.report_path = None
        self.category = None
        self.ai_review = None
        self.ai_recommendation = ""
        self.ai_error = None
        self.category_dirs = {}
        self._processing = False
        self._canvases: set = set()  # scrollable canvases (for the mouse wheel)

        # Reviewer question variables
        self.var_audience = tk.StringVar(value="campus_wide")
        self.var_access = tk.StringVar(value="limits_some")
        self.var_legal = tk.StringVar(value="medium")
        self.var_deploy = tk.StringVar(value="department")
        self.var_override = tk.StringVar(value="")  # empty = use suggested

        # Load reviewer/organization settings (first run shows setup dialog)
        first_run = settings_manager.is_first_run()
        self.settings = settings_manager.load_settings()

        self._init_style()
        self._build_ui()
        self._ensure_dirs()
        self._bind_scroll()

        if first_run:
            self.after(200, self._first_run_setup)

    def _init_style(self):
        """Flat, modern ttk widgets (progress bar + scrollbars)."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=BG_SECTION,
            background=ACCENT,
            bordercolor=BG_SECTION,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=8,
            borderwidth=0,
        )
        style.configure(
            "Slim.Vertical.TScrollbar",
            background="#cbd5e1",
            troughcolor=BG_APP,
            bordercolor=BG_APP,
            arrowsize=12,
            relief="flat",
        )
        style.map("Slim.Vertical.TScrollbar", background=[("active", "#94a3b8")])

    def _first_run_setup(self):
        dlg = SettingsDialog(self, first_run=True)
        self.wait_window(dlg)
        self.settings = settings_manager.load_settings()
        self._refresh_identity()

    def _open_settings(self):
        dlg = SettingsDialog(self, first_run=False)
        self.wait_window(dlg)
        if dlg.saved:
            self.settings = settings_manager.load_settings()
            self._refresh_identity()
            self._status("Settings saved. New reports will use the updated details.", C_SUCCESS)

    def _refresh_identity(self):
        short = self.settings.get("org_short") or "VPAT"
        self.title(f"{short} VPAT Reviewer")
        if hasattr(self, "lbl_org_badge"):
            self.lbl_org_badge.config(text=short)

    def _ensure_dirs(self):
        try:
            (
                self.vpats_dir,
                self.reports_dir,
                self.ai_prompts_dir,
                self.ai_responses_dir,
            ) = _ensure_folders()
            self.category_dirs = _ensure_category_dirs(self.reports_dir)
        except Exception as e:
            messagebox.showerror(
                "Folder Error",
                f"Could not create Desktop folders:\n{e}\n\n"
                "Reports will be saved to the current directory.",
            )
            self.vpats_dir = Path(".")
            self.reports_dir = Path(".")
            self.ai_prompts_dir = Path(".")
            self.ai_responses_dir = Path(".")
            self.category_dirs = _ensure_category_dirs(self.reports_dir)

    # ── Display sizing / DPI ─────────────────────────────────────────────────────

    def _px(self, n: int) -> int:
        """Scale a raw-pixel dimension by the display's DPI factor.

        Point-sized fonts grow with `tk scaling`, but frames sized in raw pixels
        (with `pack_propagate(False)`) do not — so without this they'd clip the
        larger text on a scaled display. Use it for those fixed-height frames.
        """
        return int(round(n * self._dpi_scale))

    def _fit_to_work_area(self) -> None:
        """Size and centre the window within the usable screen (taskbar excluded).

        Scales the base size by the DPI factor so it keeps its logical size on a
        high-DPI display, then clamps both the size and the minimum to the work
        area — so the window never exceeds the screen and can always be shrunk to
        fit, with the scroll regions handling anything that no longer fits.
        """
        left, top, area_w, area_h = work_area(self, margin=self._px(48))

        w = min(int(1460 * self._dpi_scale), area_w)
        h = min(int(1000 * self._dpi_scale), area_h)
        # The minimum is deliberately NOT scaled up: with the panes and dialogs
        # now scrollable, a modest floor lets the window shrink to fit small or
        # heavily scaled screens. Clamp so it can never exceed the work area.
        self.minsize(min(1120, area_w), min(740, area_h))

        x = left + max(0, (area_w - w) // 2)
        y = top + max(0, (area_h - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Mouse-wheel scrolling ────────────────────────────────────────────────────

    def _bind_scroll(self):
        # One interpreter-global binding scrolls whichever registered canvas the
        # pointer is over (the workflow pane, the summary list, and the dialogs).
        self.bind_all("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, event):
        # Scroll whichever managed canvas the pointer is over. Walk up from the
        # widget under the cursor so hovering a label/frame inside still scrolls.
        w = event.widget
        while w is not None:
            if w in self._canvases:
                w.yview_scroll(-1 * (event.delta // 120), "units")
                return
            w = getattr(w, "master", None)

    def _scrollable(self, parent, bg=BG_APP):
        """A vertically scrollable region: returns (canvas, inner_frame).

        Thin wrapper over the shared ``make_scrollable`` (also used by the
        dialogs) that registers the canvas in this window's wheel-scroll set.
        """
        return make_scrollable(parent, self._canvases, bg)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_body()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HEADER, height=self._px(66))
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self.lbl_org_badge = tk.Label(
            hdr,
            text=self.settings.get("org_short", "SFBRN"),
            font=(FONT, 18, "bold"),
            bg=BG_HEADER,
            fg=FG_WHITE,
        )
        self.lbl_org_badge.pack(side="left", padx=(18, 10), pady=14)

        tk.Label(
            hdr,
            text="VPAT Accessibility Compliance Reviewer",
            font=(FONT, 11),
            bg=BG_HEADER,
            fg="#9fc0e0",
        ).pack(side="left", pady=14)

        self._hdr_btn(hdr, "⚙  Settings", self._open_settings).pack(
            side="right", padx=(4, 14), pady=16
        )
        self._hdr_btn(hdr, "Open VPATs Folder", self._open_vpats_folder).pack(
            side="right", padx=4, pady=16
        )
        self._hdr_btn(hdr, "Open Reports Folder", self._open_reports_folder).pack(
            side="right", padx=4, pady=16
        )

        # Thin accent underline for a crisper edge.
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

    def _hdr_btn(self, parent, text, command):
        b = FlatButton(
            parent,
            text=text,
            font=(FONT, 8, "bold"),
            bg="#24507a",
            fg=FG_WHITE,
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            activebackground="#2d6a9f",
            activeforeground=FG_WHITE,
            command=command,
        )
        b.bind("<Enter>", lambda e: b.config(bg="#2d6a9f"))
        b.bind("<Leave>", lambda e: b.config(bg="#24507a"))
        return b

    def _build_body(self):
        # Resizable two-pane split: workflow (left) | crisp summary (right).
        paned = tk.PanedWindow(
            self,
            orient="horizontal",
            bg=BORDER,
            sashwidth=6,
            sashrelief="flat",
            bd=0,
            sashpad=0,
            opaqueresize=True,
        )
        paned.pack(fill="both", expand=True)

        left = tk.Frame(paned, bg=BG_APP)
        right = tk.Frame(paned, bg=BG_PANEL)
        paned.add(left, minsize=560, stretch="always")
        paned.add(right, minsize=340, stretch="always")
        # Give the workflow ~62% of the width on first layout.
        self.after(60, lambda: self._init_sash(paned))

        self._build_workflow(left)
        self._build_summary_panel(right)

    def _init_sash(self, paned):
        try:
            # Flush the fit-to-screen geometry first so winfo_width() reflects the
            # real window size before we place the sash at ~62% of it.
            self.update_idletasks()
            paned.sash_place(0, int(self.winfo_width() * 0.62), 1)
        except Exception:
            pass

    def _build_workflow(self, parent):
        # The three workflow cards live in a vertically scrollable region so the
        # bottom "Generate Report" / "Save Report As…" buttons stay reachable even
        # when the window is short or zoomed in. The scrollbar auto-hides when the
        # cards fit, so on a normal-sized window this looks exactly as before and
        # the mouse wheel simply does nothing until there's overflow to scroll.
        _canvas, body = self._scrollable(parent, bg=BG_APP)

        # Equal 16px gaps: top of card1, between each pair, matched top+bottom.
        self._card(body, 1, "Upload VPAT Document", self._build_upload_card).pack(
            fill="x", padx=20, pady=(16, 8)
        )
        self._card(body, 2, "Impact Assessment Questions", self._build_questions_card).pack(
            fill="x", padx=20, pady=8
        )
        self._card(body, 3, "Generate Report", self._build_generate_card).pack(
            fill="x", padx=20, pady=8
        )

    def _card(self, parent, num, title: str, builder_fn) -> tk.Frame:
        """A modern white card: hairline border, number chip + title header."""
        outer = tk.Frame(parent, bg=BG_APP)
        card = tk.Frame(outer, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1, bd=0)
        card.pack(fill="x")

        head = tk.Frame(card, bg=BG_CARD)
        head.pack(fill="x", padx=18, pady=(14, 2))
        tk.Label(head, text=f" {num} ", font=(FONT, 10, "bold"), bg=ACCENT, fg=FG_WHITE).pack(
            side="left"
        )
        tk.Label(head, text=title, font=(FONT, 12, "bold"), bg=BG_CARD, fg=FG_NAVY).pack(
            side="left", padx=10
        )
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(10, 0))

        content = tk.Frame(card, bg=BG_CARD)
        content.pack(fill="x")
        builder_fn(content)
        return outer

    # ── Upload card ────────────────────────────────────────────────────────────

    def _build_upload_card(self, parent):
        drop = tk.Frame(
            parent, bg=BG_SECTION, height=self._px(88), highlightbackground=BORDER, highlightthickness=1
        )
        drop.pack(fill="x", padx=18, pady=(14, 8))
        drop.pack_propagate(False)

        self.lbl_drop = tk.Label(
            drop,
            text="Drag and drop a VPAT here, or click the button below",
            font=(FONT, 10),
            bg=BG_SECTION,
            fg=FG_CAPTION,
        )
        self.lbl_drop.pack(expand=True)

        btn_row = tk.Frame(parent, bg=BG_CARD)
        btn_row.pack(fill="x", padx=18, pady=(0, 16))

        self._pri_btn(btn_row, "Upload VPAT  (PDF / Word / TXT)", self._browse_vpat).pack(
            side="left", padx=(0, 10)
        )

        self.lbl_file = tk.Label(
            btn_row, text="No file selected", font=(FONT, 9), bg=BG_CARD, fg=FG_CAPTION
        )
        self.lbl_file.pack(side="left", pady=4)

    # ── Segmented control (pill toggle group) ───────────────────────────────────

    def _segmented(self, parent, var, options):
        """A row of connected toggle buttons bound to ``var`` (a StringVar).

        Replaces a radio group: exactly one option is "on" (filled accent); the
        rest are light. Clicking one sets the var and restyles the row.
        """
        SEL_BG, SEL_FG = ACCENT, FG_WHITE
        OFF_BG, OFF_FG = BG_SECTION, FG_NAVY
        HOV_BG = ACCENT_SFT

        row = tk.Frame(parent, bg=BG_CARD)
        buttons: list[tuple[FlatButton, str]] = []

        def restyle():
            cur = var.get()
            for b, val in buttons:
                on = val == cur
                b.config(
                    bg=SEL_BG if on else OFF_BG,
                    fg=SEL_FG if on else OFF_FG,
                    activebackground=SEL_BG if on else HOV_BG,
                    activeforeground=SEL_FG if on else OFF_FG,
                )

        for label, value in options:
            b = FlatButton(
                row,
                text=label,
                font=(FONT, 9),
                relief="flat",
                bd=0,
                padx=15,
                pady=7,
                cursor="hand2",
                highlightbackground=BORDER,
                highlightthickness=1,
                command=lambda v=value: (var.set(v), restyle()),
            )
            b.pack(side="left", padx=(0, 2))
            b.bind(
                "<Enter>",
                lambda e, bb=b, vv=value: bb.config(bg=HOV_BG) if var.get() != vv else None,
            )
            b.bind("<Leave>", lambda e: restyle())
            buttons.append((b, value))

        restyle()
        row._restyle = restyle  # let external var changes refresh the row
        return row

    # ── Questions card ─────────────────────────────────────────────────────────

    def _build_questions_card(self, parent):
        pad = {"padx": 20, "pady": (10, 3)}

        questions = [
            (
                "How many users will this product serve?",
                "var_audience",
                [
                    ("1 user — individual use", "individual"),
                    ("2–20 users — small team", "small_team"),
                    ("21+ users — campus-wide", "campus_wide"),
                ],
            ),
            (
                "How does this product affect access for users with disabilities?",
                "var_access",
                [
                    ("Does not limit access", "no_limit"),
                    ("Limits some access", "limits_some"),
                    ("Denies access to features", "denies_access"),
                ],
            ),
            (
                "What is the legal exposure level for this product?",
                "var_legal",
                [
                    ("Low — minimal ADA/504 risk", "low"),
                    ("Medium — moderate risk", "medium"),
                    ("High — significant ADA/504 risk", "high"),
                ],
            ),
            (
                "What is the deployment scope?",
                "var_deploy",
                [
                    ("Individual", "individual"),
                    ("Department", "department"),
                    ("Campus-wide", "campus_wide"),
                ],
            ),
        ]

        for q_text, var_name, options in questions:
            tk.Label(
                parent,
                text=q_text,
                font=(FONT, 9, "bold"),
                bg=BG_CARD,
                fg=FG_NAVY,
                wraplength=640,
                justify="left",
            ).pack(anchor="w", **pad)
            var = getattr(self, var_name)
            self._segmented(parent, var, options).pack(anchor="w", padx=20, pady=(0, 8))

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=20, pady=6)

        override_row = tk.Frame(parent, bg=BG_CARD)
        override_row.pack(fill="x", padx=20, pady=(4, 14))
        tk.Label(
            override_row,
            text="Override suggested impact level (optional):",
            font=(FONT, 9, "bold"),
            bg=BG_CARD,
            fg=FG_NAVY,
        ).pack(side="left", padx=(0, 10))
        self._segmented(
            override_row,
            self.var_override,
            [("Use suggested", ""), ("Low", "Low"), ("Medium", "Medium"), ("High", "High")],
        ).pack(side="left")

    # ── Generate card ──────────────────────────────────────────────────────────

    def _build_generate_card(self, parent):
        btn_row = tk.Frame(parent, bg=BG_CARD)
        btn_row.pack(fill="x", padx=18, pady=14)

        self.btn_generate = self._pri_btn(
            btn_row, "Generate Report", self._start_generate, state="disabled"
        )
        self.btn_generate.pack(side="left", padx=(0, 10))

        self.btn_save_as = self._ghost_btn(
            btn_row, "Save Report As…", self._save_as, state="disabled"
        )
        self.btn_save_as.pack(side="left")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            parent,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress.pack(padx=18, pady=(2, 8), fill="x")

        self.lbl_status = tk.Label(
            parent,
            text="Ready — upload a VPAT to begin.",
            font=(FONT, 9),
            bg=BG_CARD,
            fg=FG_CAPTION,
        )
        self.lbl_status.pack(anchor="w", padx=20, pady=(0, 12))

    # ── Summary side panel ───────────────────────────────────────────────────────

    def _build_summary_panel(self, parent):
        bar = tk.Frame(parent, bg=BG_HEADER, height=self._px(40))
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(
            bar, text="Review Summary", font=(FONT, 11, "bold"), bg=BG_HEADER, fg=FG_WHITE
        ).pack(side="left", padx=16, pady=8)
        tk.Frame(parent, bg=ACCENT, height=2).pack(fill="x")

        holder = tk.Frame(parent, bg=BG_PANEL)
        holder.pack(fill="both", expand=True)

        # The action buttons (and any TAAP/Deny notice) pin to the bottom — pack
        # them first with side="bottom" so they always reserve their space. All
        # the summary content — verdict, tiles, facts, score message, and the
        # barrier list — lives in one scroll region above, so nothing is ever cut
        # off on a short or scaled window. The scrollbar auto-hides when it fits.
        self.sum_bottom = tk.Frame(holder, bg=BG_PANEL)
        self.sum_bottom.pack(side="bottom", fill="x")
        self.sum_canvas, self.sum_content = self._scrollable(holder, bg=BG_PANEL)

        self._render_summary_placeholder()

    def _clear_summary(self):
        """Empty the scroll content and the pinned footer, and reset the scroll
        position, before rendering a fresh summary or the placeholder."""
        for region in (self.sum_content, self.sum_bottom):
            for w in region.winfo_children():
                w.destroy()
        self.sum_canvas.yview_moveto(0)

    def _render_summary_placeholder(self):
        self._clear_summary()
        wrap = tk.Frame(self.sum_content, bg=BG_PANEL)
        wrap.pack(fill="x", padx=20, pady=26)
        tk.Label(wrap, text="\U0001f4cb", font=(FONT, 32), bg=BG_PANEL, fg="#9fb3c8").pack(
            pady=(0, 10)
        )
        tk.Label(
            wrap, text="No review yet", font=(FONT, 12, "bold"), bg=BG_PANEL, fg=FG_NAVY
        ).pack()
        tk.Label(
            wrap,
            text="Upload a VPAT, answer the questions, and click "
            "Generate Report. The verdict and a quick-read summary "
            "appear here.",
            font=(FONT, 9),
            bg=BG_PANEL,
            fg=FG_CAPTION,
            wraplength=300,
            justify="center",
        ).pack(pady=(6, 18))

        legend = tk.Frame(
            self.sum_content, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1
        )
        legend.pack(fill="x", padx=16, pady=(0, 16))
        tk.Label(
            legend, text="VERDICT CATEGORIES", font=(FONT, 8, "bold"), bg=BG_CARD, fg=FG_CAPTION
        ).pack(anchor="w", padx=12, pady=(10, 4))
        for cat in CATEGORIES:
            color, glyph, meaning = CATEGORY_META[cat]
            row = tk.Frame(legend, bg=BG_CARD)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=f" {glyph} ", font=(FONT, 9, "bold"), bg=color, fg=FG_WHITE).pack(
                side="left"
            )
            col = tk.Frame(row, bg=BG_CARD)
            col.pack(side="left", padx=8, fill="x", expand=True)
            tk.Label(
                col, text=cat, font=(FONT, 9, "bold"), bg=BG_CARD, fg=FG_NAVY, anchor="w"
            ).pack(fill="x")
            tk.Label(
                col,
                text=meaning,
                font=(FONT, 8),
                bg=BG_CARD,
                fg=FG_CAPTION,
                anchor="w",
                wraplength=230,
                justify="left",
            ).pack(fill="x")
        tk.Frame(legend, bg=BG_CARD, height=6).pack()

    def _stat_tile(self, parent, caption, value, color):
        tile = tk.Frame(parent, bg=color)
        tile.pack(side="left", padx=(0, 8), fill="x", expand=True)
        tk.Label(tile, text=caption.upper(), font=(FONT, 8, "bold"), bg=color, fg=FG_ONACC).pack(
            padx=12, pady=(8, 0), anchor="w"
        )
        tk.Label(tile, text=value, font=(FONT, 20, "bold"), bg=color, fg=FG_WHITE).pack(
            padx=12, pady=(0, 8), anchor="w"
        )

    def _verdict_source(self) -> str:
        """Who actually decided the verdict — the model, or the offline rules."""
        if self.ai_review is not None and self.ai_review.is_verdict:
            return "Amazon Bedrock"
        return "Deterministic rules"

    def _populate_summary(self):
        self._clear_summary()

        data = self.vpat_data
        score = self.score_info.get("score")
        level = self.impact_info.get(
            "final_level", self.impact_info.get("suggested_level", "Medium")
        )
        color, glyph, meaning = CATEGORY_META.get(
            self.category, CATEGORY_META["Needs Manual Review"]
        )

        # (1) Verdict banner
        banner = tk.Frame(self.sum_content, bg=color)
        banner.pack(fill="x", padx=16, pady=(16, 10))
        tk.Label(banner, text=glyph, font=(FONT, 24, "bold"), bg=color, fg=FG_WHITE).pack(
            side="left", padx=(14, 8), pady=12
        )
        vt = tk.Frame(banner, bg=color)
        vt.pack(side="left", pady=12, fill="x", expand=True)
        tk.Label(
            vt,
            text=self.category.upper(),
            font=(FONT, 14, "bold"),
            bg=color,
            fg=FG_WHITE,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            vt,
            text=meaning,
            font=(FONT, 8),
            bg=color,
            fg=FG_ONACC,
            wraplength=250,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        # (2) Stat tiles
        tiles = tk.Frame(self.sum_content, bg=BG_PANEL)
        tiles.pack(fill="x", padx=16, pady=(0, 10))
        score_str = f"{score}%" if score is not None else "N/A"
        score_color = C_GREEN if (score or 0) >= 75 else (C_ORANGE if (score or 0) >= 50 else C_RED)
        self._stat_tile(tiles, "Compliance", score_str, score_color)
        self._stat_tile(tiles, "Impact", level.upper(), IMPACT_COLORS.get(level, C_ORANGE))

        # (3) Key facts
        aa_barriers = [
            c
            for c in data.criteria
            if c.level == "AA" and c.normalized_status not in ("Supports", "Not Applicable")
        ]
        facts = tk.Frame(
            self.sum_content, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1
        )
        facts.pack(fill="x", padx=16, pady=(0, 10))
        rows = [
            ("Product", data.product_name or "—"),
            ("Vendor", data.vendor_name or "—"),
            ("Report Date", data.vendor_report_date_raw or "—"),
            ("AA Barriers", str(len(aa_barriers))),
            ("Filed Under", CATEGORY_FOLDER.get(self.category, "—")),
            # Who decided. Without this, "did the AI actually run?" is
            # unanswerable from the app — and for a long time the answer in the
            # shipped exe was silently "no".
            ("Verdict by", self._verdict_source()),
        ]
        for i, (lbl, val) in enumerate(rows):
            r = tk.Frame(facts, bg=BG_CARD)
            r.pack(fill="x", padx=10, pady=(8 if i == 0 else 2, 8 if i == len(rows) - 1 else 2))
            tk.Label(
                r, text=lbl, font=(FONT, 8, "bold"), bg=BG_CARD, fg=FG_CAPTION, width=12, anchor="w"
            ).pack(side="left")
            tk.Label(
                r,
                text=val,
                font=(FONT, 9),
                bg=BG_CARD,
                fg=FG_INK,
                anchor="w",
                wraplength=210,
                justify="left",
            ).pack(side="left", fill="x", expand=True)

        # (4) Score message
        msg = (self.score_info.get("message") or "").strip()
        if msg:
            mb = tk.Frame(self.sum_content, bg=ACCENT_SFT)
            mb.pack(fill="x", padx=16, pady=(0, 10))
            tk.Label(
                mb,
                text=msg,
                font=(FONT, 9),
                bg=ACCENT_SFT,
                fg=FG_INK,
                wraplength=280,
                justify="left",
            ).pack(anchor="w", padx=12, pady=9)

        # (5) All barriers — part of the single scroll column
        tk.Label(
            self.sum_content,
            text=f"BARRIERS  ({len(aa_barriers)})",
            font=(FONT, 8, "bold"),
            bg=BG_PANEL,
            fg=FG_CAPTION,
            anchor="w",
        ).pack(fill="x", padx=18, pady=(6, 2))
        blist = tk.Frame(
            self.sum_content, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1
        )
        blist.pack(fill="x", padx=16, pady=(0, 10), anchor="n")
        if not aa_barriers:
            tk.Label(
                blist, text="No WCAG AA barriers found. ✓", font=(FONT, 9), bg=BG_CARD, fg=C_GREEN
            ).pack(anchor="w", padx=12, pady=10)
        else:
            for k, c in enumerate(aa_barriers):
                r = tk.Frame(blist, bg=BG_CARD)
                r.pack(fill="x", padx=10, pady=(7 if k == 0 else 3, 3))
                dot = tk.Label(
                    r, text="●", font=(FONT, 8), bg=BG_CARD, fg=_status_color(c.normalized_status)
                )
                dot.pack(side="left", anchor="n", padx=(0, 6), pady=1)
                col = tk.Frame(r, bg=BG_CARD)
                col.pack(side="left", fill="x", expand=True)
                tk.Label(
                    col,
                    text=f"{c.criterion_id}  {c.title}",
                    font=(FONT, 8, "bold"),
                    bg=BG_CARD,
                    fg=FG_INK,
                    wraplength=250,
                    justify="left",
                    anchor="w",
                ).pack(fill="x")
                tk.Label(
                    col,
                    text=c.normalized_status,
                    font=(FONT, 8),
                    bg=BG_CARD,
                    fg=_status_color(c.normalized_status),
                    anchor="w",
                ).pack(fill="x")
                if k < len(aa_barriers) - 1:
                    tk.Frame(blist, bg="#f1f5f9", height=1).pack(fill="x", padx=10)

        # (6) TAAP / Deny notice  (fixed — bottom region)
        if self.category in ("Need TAAP", "Deny"):
            note = tk.Frame(
                self.sum_bottom, bg="#fdf0f0", highlightbackground=color, highlightthickness=1
            )
            note.pack(fill="x", padx=16, pady=(6, 10))
            text = (
                "A Temporary Alternative Access Plan (TAAP) is required before approval."
                if self.category == "Need TAAP"
                else "Do not deploy — remediation is required before this "
                "product can be reconsidered."
            )
            tk.Label(
                note,
                text=text,
                font=(FONT, 9, "bold"),
                bg="#fdf0f0",
                fg=color,
                wraplength=270,
                justify="left",
            ).pack(anchor="w", padx=12, pady=9)

        # (7) Actions  (fixed — bottom region)
        actions = tk.Frame(self.sum_bottom, bg=BG_PANEL)
        actions.pack(fill="x", padx=16, pady=(4, 16))
        if self.report_path and Path(self.report_path).exists():
            self._pri_btn(
                actions,
                "Open Report PDF",
                lambda: os.startfile(str(self.report_path)) if os.name == "nt" else None,
            ).pack(fill="x", pady=(0, 6))
        cat_dir = self.category_dirs.get(self.category)
        if cat_dir:
            self._ghost_btn(
                actions,
                f"Open “{CATEGORY_FOLDER[self.category]}” Folder",
                lambda d=cat_dir: self._open_folder(d),
            ).pack(fill="x")

    # ── Button helpers ─────────────────────────────────────────────────────────

    def _pri_btn(self, parent, text, command, state="normal"):
        btn = FlatButton(
            parent,
            text=text,
            font=(FONT, 9, "bold"),
            bg=ACCENT,
            fg=FG_WHITE,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            state=state,
            command=command,
            activebackground=ACCENT_HOV,
            activeforeground=FG_WHITE,
            disabledforeground="#c7d2e5",
        )
        btn.bind(
            "<Enter>",
            lambda e: btn.configure(bg=ACCENT_HOV) if str(btn["state"]) != "disabled" else None,
        )
        btn.bind(
            "<Leave>",
            lambda e: btn.configure(bg=ACCENT) if str(btn["state"]) != "disabled" else None,
        )
        return btn

    def _ghost_btn(self, parent, text, command, state="normal"):
        btn = FlatButton(
            parent,
            text=text,
            font=(FONT, 9, "bold"),
            bg=ACCENT_SFT,
            fg=ACCENT,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            state=state,
            command=command,
            activebackground="#dbe7fb",
            activeforeground=ACCENT,
            disabledforeground="#a9bad6",
        )
        btn.bind(
            "<Enter>",
            lambda e: btn.configure(bg="#dbe7fb") if str(btn["state"]) != "disabled" else None,
        )
        btn.bind(
            "<Leave>",
            lambda e: btn.configure(bg=ACCENT_SFT) if str(btn["state"]) != "disabled" else None,
        )
        return btn

    # ── Actions ────────────────────────────────────────────────────────────────

    def _browse_vpat(self):
        path = filedialog.askopenfilename(
            title="Select VPAT Document",
            filetypes=[
                ("Supported files", "*.pdf *.docx *.doc *.txt"),
                ("PDF files", "*.pdf"),
                ("Word documents", "*.docx *.doc"),
                ("Text files", "*.txt"),
            ],
        )
        if path:
            self._load_vpat(path)

    def _load_vpat(self, path: str):
        self.vpat_path.set(path)
        fname = Path(path).name
        ext = Path(path).suffix.upper().lstrip(".")
        self.lbl_file.config(text=f"{fname}  [{ext}]", fg=FG_NAVY, font=(FONT, 9, "bold"))
        self.lbl_drop.config(text=f"Loaded: {fname}", fg=FG_NAVY)
        self.btn_generate.config(state="normal", bg=ACCENT)
        self._status("File loaded. Fill in the questions above, then click Generate Report.")

    def _status(self, msg: str, color: str = FG_CAPTION):
        self.lbl_status.config(text=msg, fg=color)
        self.update_idletasks()

    def _set_progress(self, pct: int, msg: str = ""):
        self.progress_var.set(pct)
        if msg:
            self._status(msg)
        self.update_idletasks()

    def _start_generate(self):
        if self._processing:
            return
        path = self.vpat_path.get()
        if not path or not Path(path).exists():
            messagebox.showwarning("No File", "Please upload a VPAT document first.")
            return
        self._processing = True
        self.btn_generate.config(state="disabled")
        self.btn_save_as.config(state="disabled")
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        try:
            self._generate()
        except Exception as e:
            logger.exception("Pipeline failed")
            self.after(0, lambda: self._on_error(str(e)))
        finally:
            self._processing = False
            self.after(0, lambda: self.btn_generate.config(state="normal"))

    def _persist_ai_io(self, stem, prompt_text, assessment):
        """Save the exact prompt sent to Bedrock and the assessment it produced.

        Writes to the two Desktop folders (AI Prompts / AI Responses) so every
        run has an auditable trail. Never raises — logging must not block a report.

        The record is ``assessment.to_dict()`` verbatim: it already carries the
        model id, the confidence, the error when there was one, and the model's
        raw reply. Copying fields out by hand here is how they get forgotten.
        """
        try:
            prompts_dir = getattr(self, "ai_prompts_dir", None)
            responses_dir = getattr(self, "ai_responses_dir", None)
            if prompts_dir is None or responses_dir is None:
                return
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            model = self.settings.get("bedrock_model_id", "")

            if prompt_text:
                (prompts_dir / f"{stem}.txt").write_text(
                    "# Prompt sent to Amazon Bedrock\n"
                    + f"# {stamp} | model: {model}\n\n"
                    + prompt_text,
                    encoding="utf-8",
                )

            record = {
                "timestamp": stamp,
                "region": self.settings.get("bedrock_region", ""),
            }
            if assessment is not None:
                record.update(assessment.to_dict())
            (responses_dir / f"{stem}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        except Exception as e:  # noqa: BLE001 - logging must never break generation
            logger.warning("Could not save AI prompt/response logs: %s", e)

    def _generate(self):

        self.after(0, lambda: self._set_progress(5, "Reading document…"))

        path = self.vpat_path.get()
        data = parse_vpat(path)
        self.vpat_data = data

        self.after(0, lambda: self._set_progress(30, "Analysing WCAG criteria…"))

        score_info = compliance_score(data)
        self.score_info = score_info

        self.after(0, lambda: self._set_progress(50, "Calculating impact level…"))

        answers = {
            "audience": self.var_audience.get(),
            "access_impact": self.var_access.get(),
            "legal_exposure": self.var_legal.get(),
            "deployment": self.var_deploy.get(),
        }
        barriers = get_aa_barriers(data)
        impact_info = calculate_impact(answers, barriers, score_info)

        # Apply override
        override = self.var_override.get()
        if override:
            impact_info["final_level"] = override
            impact_info["rationale"].insert(
                0, f"Reviewer manually overrode suggested impact level to: {override}."
            )
        else:
            impact_info["final_level"] = impact_info["suggested_level"]

        # Verdict source: Amazon Bedrock decides when AI is enabled; the
        # deterministic classifier is the offline fallback (and the fallback on
        # any Bedrock/creds failure, so a report is always produced).
        good_cut = int(self.settings.get("threshold", 90) or 90)
        self.ai_review = None
        self.ai_recommendation = ""  # reset per run: never carry a prior doc's advice
        self.ai_error = None
        used_ai = False
        # Correlate the saved prompt/response with the report by a shared stem.
        _stem_name = (_safe_filename(data.product_name or "Product")[:50]).strip() or "Product"
        ai_stem = _stem_name + "_" + datetime.now().strftime("%Y-%m-%d_%H%M%S")
        if self.settings.get("use_ai", True):
            self.after(0, lambda: self._set_progress(58, "Consulting Amazon Bedrock…"))
            review_obj = ReviewResult(
                document=data,
                score=score_info,
                impact=impact_info,
                barriers=barriers,
                answers=answers,
            )
            request = None
            prompt_text = ""
            try:
                request = build_assessment_request(review_obj)
                prompt_text = request.prompt
            except AssessmentError as e:  # an unpackaged or malformed rubric
                logger.warning("Could not build the AI prompt: %s", e)

            # assess_result never raises: a failed call, or a reply we cannot read
            # as a verdict, records a "Not Assessed" assessment instead.
            assessor = BedrockAssessor(BedrockConfig.from_settings(self.settings))
            assess_result(review_obj, assessor=assessor, request=request)
            ai = review_obj.assessment
            self.ai_review = ai
            self._persist_ai_io(ai_stem, prompt_text, ai)

            if ai is not None and ai.is_verdict:
                self.category = ai.category
                level = _impact_from_risk(ai.risk_level)
                if level and not override:  # a manual override still wins the impact level
                    impact_info["final_level"] = level
                bullets = _rationale_bullets(ai)
                if bullets:
                    impact_info["rationale"] = bullets
                # The one-pager prints this alone under RECOMMENDATION, where the
                # rationale bullets would not do: a decision sheet needs the
                # action, not the finding.
                self.ai_recommendation = ai.recommendation or ""
                used_ai = True
            else:
                self.ai_error = (ai.error or ai.reason) if ai else "no assessment was produced"
                logger.warning(
                    "AI review unavailable (%s); using deterministic verdict.", self.ai_error
                )

        if not used_ai:
            # Deterministic five-folder heuristic (offline / fallback).
            self.category = classify_report(
                score_info.get("score"),
                impact_info["final_level"],
                len(barriers),
                self.var_access.get(),
                good_cut,
            )

        self.impact_info = impact_info

        self.after(0, lambda: self._set_progress(65, "Building PDF report…"))

        # Copy VPAT to local folder
        try:
            today = date.today().strftime("%Y-%m-%d")
            safe = "".join(
                c if c.isalnum() or c in "-_ " else "_" for c in (data.product_name or "Product")
            ).strip()
            ext = Path(path).suffix
            dest = self.vpats_dir / f"{safe}_{today}{ext}"
            if not dest.exists():
                shutil.copy2(path, dest)
        except Exception as e:
            logger.warning(f"Could not copy VPAT: {e}")

        # Generate into the matching verdict folder.
        product = data.product_name or "Product"
        cat_dir = self.category_dirs.get(self.category, self.reports_dir)
        out_path = _next_report_path(cat_dir, product)

        # Logo path (frozen-aware: next to the .exe when packaged)
        import sys as _sys

        if getattr(_sys, "frozen", False):
            script_dir = Path(_sys.executable).parent
        else:
            script_dir = Path(__file__).parent
        logo_candidates = [
            script_dir / "assets" / "SFBRN_Logo.png",
            script_dir / "SFBRN_Logo.png",
            Path("assets") / "SFBRN_Logo.png",
        ]
        logo_path = ""
        # A custom logo chosen in Settings takes priority over the bundled one
        custom_logo = self.settings.get("logo_path", "")
        if custom_logo and Path(custom_logo).exists():
            logo_path = custom_logo
        else:
            for lp in logo_candidates:
                if lp.exists():
                    logo_path = str(lp)
                    break

        # Route through the ReportRenderer port so the Settings "Report style"
        # toggle picks the renderer (full report vs one-page decision sheet).
        renderer = renderer_for(self.settings)
        renderer.render(
            ReportInputs(
                document=data,
                score=dict(score_info),
                impact=dict(impact_info),
                answers=answers,
                logo_path=logo_path,
                settings=self.settings,
                verdict=self.category or "",
                recommendation=self.ai_recommendation,
            ),
            str(out_path),
        )

        # Post-generation PDF validation. Each renderer validates its own output:
        # the full report checks for required sections the one-pager omits by
        # design, so validating a one-pager with validate_report would fail it.
        self.after(0, lambda: self._set_progress(92, "Validating PDF…"))
        try:
            ok, problems = renderer.validate(str(out_path))
            if not ok:
                logger.error("PDF validation problems: %s", problems)
                self.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Report Validation",
                        "The report was generated but validation flagged:\n• "
                        + "\n• ".join(problems[:6]),
                    ),
                )
        except Exception as e:
            logger.warning("PDF validation could not run: %s", e)

        self.report_path = out_path

        self.after(0, lambda: self._set_progress(96, "Recording the run…"))
        self._record_run(
            ReviewResult(
                document=data,
                score=score_info,
                impact=impact_info,
                barriers=barriers,
                answers=answers,
                output_path=str(out_path),
                assessment=self.ai_review,
                verdict=self.category or "",
                recommendation=self.ai_recommendation,
            ),
            source_path=path,
            used_ai=used_ai,
            ai_stem=ai_stem,
        )

        self.after(0, lambda: self._set_progress(100, "Report generated successfully."))
        self.after(0, self._on_success)

    def _record_run(self, run, *, source_path, used_ai, ai_stem):
        """Write the parsed-record sidecar and append the run to the audit log.

        Never raises: both are bookkeeping, and the report already exists on disk
        by the time we get here. Losing the row must not lose the report or show
        the reviewer an error about a file they did not ask for.

        ``verdict_source`` is decided here because this is the only place that
        knows it: ``self.category`` is the same kind of string whether Bedrock
        produced it or ``classify_report`` did after Bedrock was unreachable, and
        that difference is exactly what an auditor needs (§7b).
        """
        try:
            write_json(run, str(Path(run.output_path).with_suffix(".json")))
        except Exception as e:  # noqa: BLE001 - the record is not the report
            logger.warning("Could not write the parsed-record JSON: %s", e)

        try:
            log = audit.log_for(self.settings)
            if log is None:
                return
            responses_dir = getattr(self, "ai_responses_dir", None)
            ai_response_path = ""
            if used_ai and responses_dir is not None:
                candidate = responses_dir / f"{ai_stem}.json"
                if candidate.exists():
                    ai_response_path = str(candidate)
            log.record(
                build_audit_event(
                    run,
                    source_path=source_path,
                    settings=self.settings,
                    verdict_source="ai" if used_ai else "offline",
                    ai_response_path=ai_response_path,
                )
            )
        except Exception as e:  # noqa: BLE001 - the log must never break a review
            logger.warning("Could not append to the audit log: %s", e)

    def _on_success(self):
        self._populate_summary()
        self.btn_save_as.config(state="normal")
        note = " (AI unavailable — deterministic verdict)" if self.ai_error else ""
        self._status(
            f"Done — verdict: {self.category}. Filed under "
            f"“{CATEGORY_FOLDER.get(self.category, '')}”.{note}",
            C_SUCCESS,
        )

    def _on_error(self, msg: str):
        self._status(f"Error: {msg}", color=C_RED)
        self.progress_var.set(0)
        messagebox.showerror(
            "Processing Error",
            f"An error occurred during report generation:\n\n{msg}\n\n"
            "Please check that the file is a valid VPAT document and try again.",
        )

    def _save_as(self):
        if not self.report_path or not Path(self.report_path).exists():
            messagebox.showwarning("No Report", "Generate a report first.")
            return
        dest = filedialog.asksaveasfilename(
            title="Save Report As",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=Path(self.report_path).name,
        )
        if dest:
            shutil.copy2(self.report_path, dest)
            messagebox.showinfo("Saved", f"Report saved to:\n{dest}")

    def _open_folder(self, folder: Path):
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_vpats_folder(self):
        self._open_folder(self.vpats_dir)

    def _open_reports_folder(self):
        self._open_folder(self.reports_dir)


# ── Entry point ────────────────────────────────────────────────────────────────


def _enable_dpi_awareness() -> None:
    """Tell Windows this process renders at native pixels, so it stops
    bitmap-stretching the window on displays scaled above 100% (the cause of the
    blurry, oversized window whose bottom buttons fall off the screen).

    Must run *before* the first Tk window is created — hence it lives here in
    ``main()`` and not in ``VPATReviewerApp.__init__`` (``super().__init__()``
    already builds the root, which is too late). No-op on non-Windows; best-effort
    on older Windows, trying the newest API first and falling back.
    """
    if sys.platform != "win32":
        return
    import ctypes

    # Each call raises on an OS too old to have it (AttributeError: symbol
    # missing) or if awareness was already set, e.g. by a manifest (OSError).
    try:
        # Per-Monitor-v2 (Win 10 1607+): crisp, per-monitor DPI. The context value
        # is pointer-sized, so pass it as c_void_p rather than a truncated int.
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor (Win 8.1+)
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # system DPI (Vista+)
    except (AttributeError, OSError):
        pass


def main() -> None:
    """Launch the desktop GUI."""
    _enable_dpi_awareness()
    app = VPATReviewerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
