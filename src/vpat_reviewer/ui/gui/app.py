"""
SFBRN VPAT Reviewer — Desktop Application
Python + Tkinter GUI
"""

import json
import logging
import os
import shutil
import subprocess
import threading
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# GUI as an adapter: import the package directly (not the legacy root shims).
from vpat_reviewer.ai.review import build_prompt, review_with_ai
from vpat_reviewer.config import settings as settings_manager
from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.scoring import compliance_score
from vpat_reviewer.domain.scoring import get_barriers as get_aa_barriers
from vpat_reviewer.parsing import parse_vpat
from vpat_reviewer.reporting.reportlab_renderer import generate_report, validate_report
from vpat_reviewer.service import ReviewResult
from vpat_reviewer.ui.gui.policy_dialog import GradingPolicyDialog

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
# Five review verdicts. Each maps to (accent colour, glyph, one-line meaning) for
# the side panel, and to an on-disk folder name reports are filed under.
CATEGORIES = [
    "Good to Go",
    "Minor Issue",
    "Needs Manual Review",
    "Need TAAP",
    "Deny",
]
CATEGORY_META = {
    "Good to Go": ("#15803d", "✓", "Meets the bar — ready to deploy as-is."),
    "Minor Issue": ("#4d7c0f", "◐", "Deployable, with a few small gaps to track."),
    "Needs Manual Review": ("#b45309", "?", "Inconclusive — a human reviewer must decide."),
    "Need TAAP": ("#c2410c", "!", "Gaps require a Technology Accessibility Action Plan."),
    "Deny": ("#b91c1c", "✕", "Fails the bar — do not deploy without remediation."),
}
CATEGORY_FOLDER = {
    "Good to Go": "Good To Go",
    "Minor Issue": "Minor Issue",
    "Needs Manual Review": "Needs Manual Review",
    "Need TAAP": "Need TAAP",
    "Deny": "Deny",
}


def classify_report(
    score, impact_level: str, barriers: int, access: str, good_cut: int = 90
) -> str:
    """Map a finished review to one of the five verdicts.

    Frontend-only heuristic (no domain change): drives which folder the report is
    filed under and what the side panel shows. ``score`` is 0–100 or ``None`` when
    it could not be computed; ``impact_level`` is Low/Medium/High.
    """
    if score is None:
        return "Needs Manual Review"
    if access == "denies_access" and impact_level == "High":
        return "Deny"
    if impact_level == "High" and score < 50:
        return "Deny"
    if impact_level == "High":
        return "Need TAAP"
    if score >= good_cut and barriers == 0:
        return "Good to Go"
    if score >= 70:
        return "Minor Issue"
    return "Needs Manual Review"


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
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.saved = False

        current = settings_manager.load_settings()
        intro = (
            "Welcome! Answer a few questions so your reports show the "
            "right organization and reviewer. You can change these any "
            "time from the Settings button."
            if first_run
            else "Update the reviewer and organization details used on generated reports."
        )
        tk.Label(
            self,
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
            tk.Label(self, text=label + ":", font=(FONT, 9, "bold"), bg=BG_CARD, fg=FG_NAVY).grid(
                row=row, column=0, padx=(16, 6), pady=4, sticky="e"
            )
            var = tk.StringVar(value=str(current.get(key, "")))
            tk.Entry(self, textvariable=var, font=(FONT, 9), width=38).grid(
                row=row, column=1, padx=(0, 16), pady=4, sticky="w"
            )
            self._vars[key] = var
            row += 1

        # Optional custom logo
        tk.Label(
            self, text="Custom logo (optional):", font=(FONT, 9, "bold"), bg=BG_CARD, fg=FG_NAVY
        ).grid(row=row, column=0, padx=(16, 6), pady=4, sticky="e")
        logo_row = tk.Frame(self, bg=BG_CARD)
        logo_row.grid(row=row, column=1, padx=(0, 16), pady=4, sticky="w")
        self._vars["logo_path"] = tk.StringVar(value=str(current.get("logo_path", "")))
        tk.Entry(logo_row, textvariable=self._vars["logo_path"], font=(FONT, 8), width=28).pack(
            side="left"
        )
        tk.Button(
            logo_row, text="Browse…", font=(FONT, 8), command=self._browse_logo, cursor="hand2"
        ).pack(side="left", padx=4)
        row += 1
        tk.Label(
            self,
            text="Leave logo blank to use the bundled default.",
            font=(FONT, 8),
            bg=BG_CARD,
            fg=FG_CAPTION,
        ).grid(row=row, column=1, padx=(0, 16), sticky="w")
        row += 1

        btn_row = tk.Frame(self, bg=BG_CARD)
        btn_row.grid(row=row, column=0, columnspan=2, pady=(12, 14))
        tk.Button(
            btn_row,
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
        tk.Button(
            btn_row,
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
            tk.Button(
                btn_row,
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
        self.geometry("1460x1000")
        self.minsize(1120, 740)
        self.configure(bg=BG_APP)
        self.resizable(True, True)

        # UI-zoom (scalable): multiplies Tk's point→pixel scaling.
        self._base_scaling = float(self.tk.call("tk", "scaling"))
        self._zoom = 1.0

        # State
        self.vpat_path = tk.StringVar(value="")
        self.vpat_data = None
        self.score_info = {}
        self.impact_info = {}
        self.report_path = None
        self.category = None
        self.ai_review = None
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
        self._bind_shortcuts()

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

    # ── Zoom / scalability ───────────────────────────────────────────────────────

    def _bind_shortcuts(self):
        self.bind("<Control-plus>", lambda e: self._set_zoom(self._zoom + 0.1))
        self.bind("<Control-equal>", lambda e: self._set_zoom(self._zoom + 0.1))
        self.bind("<Control-minus>", lambda e: self._set_zoom(self._zoom - 0.1))
        self.bind("<Control-0>", lambda e: self._set_zoom(1.0))
        self.bind_all("<MouseWheel>", self._on_wheel)

    def _set_zoom(self, factor: float):
        self._zoom = max(0.7, min(1.8, round(factor, 2)))
        self.tk.call("tk", "scaling", self._base_scaling * self._zoom)
        if hasattr(self, "lbl_zoom"):
            self.lbl_zoom.config(text=f"{int(self._zoom * 100)}%")

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

        The scrollbar auto-hides — it only appears when the content is taller
        than the viewport, so a panel that fits shows no scrollbar at all.
        """
        canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
        vsb = ttk.Scrollbar(
            parent, orient="vertical", command=canvas.yview, style="Slim.Vertical.TScrollbar"
        )
        canvas.pack(side="left", fill="both", expand=True)

        def _autohide(first, last):
            # Content fits when the whole 0..1 range is visible → hide the bar.
            if float(first) <= 0.0 and float(last) >= 1.0:
                if vsb.winfo_ismapped():
                    vsb.pack_forget()
            elif not vsb.winfo_ismapped():
                vsb.pack(side="right", fill="y", before=canvas)
            vsb.set(first, last)

        canvas.configure(yscrollcommand=_autohide)

        inner = tk.Frame(canvas, bg=bg)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self._canvases.add(canvas)
        return canvas, inner

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_body()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HEADER, height=66)
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

        # Zoom readout (Ctrl +/- / 0)
        self.lbl_zoom = tk.Label(hdr, text="100%", font=(FONT, 8), bg=BG_HEADER, fg="#6f93b5")
        self.lbl_zoom.pack(side="right", padx=(4, 8), pady=20)

        # Thin accent underline for a crisper edge.
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

    def _hdr_btn(self, parent, text, command):
        b = tk.Button(
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
            paned.sash_place(0, int(self.winfo_width() * 0.62), 1)
        except Exception:
            pass

    def _build_workflow(self, parent):
        # The workflow is STATIC — the three cards never scroll; they stay put
        # with even spacing between them. (No canvas/scrollbar here, so the mouse
        # wheel does nothing over the left pane; only the right summary scrolls.)
        body = tk.Frame(parent, bg=BG_APP)
        body.pack(side="top", fill="both", expand=True)
        self.body = body

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
            parent, bg=BG_SECTION, height=88, highlightbackground=BORDER, highlightthickness=1
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
        buttons: list[tuple[tk.Button, str]] = []

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
            b = tk.Button(
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
        bar = tk.Frame(parent, bg=BG_HEADER, height=40)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(
            bar, text="Review Summary", font=(FONT, 11, "bold"), bg=BG_HEADER, fg=FG_WHITE
        ).pack(side="left", padx=16, pady=8)
        tk.Frame(parent, bg=ACCENT, height=2).pack(fill="x")

        holder = tk.Frame(parent, bg=BG_PANEL)
        holder.pack(fill="both", expand=True)

        # Three regions: fixed top + fixed bottom pin; only the barrier list
        # (middle) scrolls. Pack bottom first so it always reserves its space.
        self.sum_bottom = tk.Frame(holder, bg=BG_PANEL)
        self.sum_bottom.pack(side="bottom", fill="x")
        self.sum_top = tk.Frame(holder, bg=BG_PANEL)
        self.sum_top.pack(side="top", fill="x")

        self.sum_mid = tk.Frame(holder, bg=BG_PANEL)
        self.sum_mid.pack(side="top", fill="both", expand=True)
        self.bar_heading = tk.Label(
            self.sum_mid, text="", font=(FONT, 8, "bold"), bg=BG_PANEL, fg=FG_CAPTION, anchor="w"
        )
        self.bar_heading.pack(fill="x", padx=18, pady=(6, 2))
        # Canvas (panel-coloured) fills the region; the white card lives *inside*
        # the scroll area sized to its content. Few barriers → the card hugs them
        # and the rest is plain panel (no empty white box, no scrollbar). Many
        # barriers → the card is taller than the viewport → it scrolls and the
        # auto-hide scrollbar appears.
        self.bar_canvas, scroll_inner = self._scrollable(self.sum_mid, bg=BG_PANEL)
        self.bar_list = tk.Frame(
            scroll_inner, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1
        )
        self.bar_list.pack(fill="x", padx=16, pady=(0, 10), anchor="n")

        self._render_summary_placeholder()

    def _render_summary_placeholder(self):
        for region in (self.sum_top, self.sum_bottom, self.bar_list):
            for w in region.winfo_children():
                w.destroy()
        self.bar_heading.config(text="")
        self.bar_list.pack_forget()  # no empty card before the first review
        wrap = tk.Frame(self.sum_top, bg=BG_PANEL)
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
            self.sum_top, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1
        )
        legend.pack(fill="x", padx=16)
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

    def _populate_summary(self):
        for region in (self.sum_top, self.sum_bottom, self.bar_list):
            for w in region.winfo_children():
                w.destroy()
        self.bar_canvas.yview_moveto(0)

        data = self.vpat_data
        score = self.score_info.get("score")
        level = self.impact_info.get(
            "final_level", self.impact_info.get("suggested_level", "Medium")
        )
        color, glyph, meaning = CATEGORY_META.get(
            self.category, CATEGORY_META["Needs Manual Review"]
        )

        # (1) Verdict banner  (fixed — top region)
        banner = tk.Frame(self.sum_top, bg=color)
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

        # (2) Stat tiles  (fixed)
        tiles = tk.Frame(self.sum_top, bg=BG_PANEL)
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
        facts = tk.Frame(self.sum_top, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        facts.pack(fill="x", padx=16, pady=(0, 10))
        rows = [
            ("Product", data.product_name or "—"),
            ("Vendor", data.vendor_name or "—"),
            ("Report Date", data.vendor_report_date_raw or "—"),
            ("AA Barriers", str(len(aa_barriers))),
            ("Filed Under", CATEGORY_FOLDER.get(self.category, "—")),
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
            mb = tk.Frame(self.sum_top, bg=ACCENT_SFT)
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

        # (5) All barriers — the ONLY scrolling region (middle)
        self.bar_heading.config(text=f"BARRIERS  ({len(aa_barriers)})")
        self.bar_list.pack(fill="x", padx=16, pady=(0, 10), anchor="n")  # re-show card
        blist = self.bar_list
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
                "A Technology Accessibility Action Plan (TAAP) is required before deployment."
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
        btn = tk.Button(
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
        btn = tk.Button(
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

    def _persist_ai_io(self, stem, prompt_text, response_text, ai, error):
        """Save the exact prompt sent to Bedrock and the response received.

        Writes to the two Desktop folders (AI Prompts / AI Responses) so every
        run has an auditable trail. Never raises — logging must not block a report.
        """
        try:
            prompts_dir = getattr(self, "ai_prompts_dir", None)
            responses_dir = getattr(self, "ai_responses_dir", None)
            if prompts_dir is None or responses_dir is None:
                return
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            model = self.settings.get("bedrock_model_id", "")
            header = f"# {stamp} | model: {model}\n\n"

            if prompt_text:
                (prompts_dir / f"{stem}.txt").write_text(
                    "# Prompt sent to Amazon Bedrock\n" + header + prompt_text,
                    encoding="utf-8",
                )

            # Single response file: metadata + parsed fields + the raw reply, all
            # in one JSON (no separate .txt, so nothing is written twice).
            record = {
                "timestamp": stamp,
                "model_id": model,
                "region": self.settings.get("bedrock_region", ""),
                "error": error,
            }
            if ai is not None:
                record.update(
                    {
                        "parsed_ok": ai.parsed_ok,
                        "verdict": ai.verdict,
                        "impact_level": ai.impact_level,
                        "summary": ai.summary,
                        "rationale": ai.rationale,
                        "recommendations": ai.recommendations,
                    }
                )
            record["raw_response"] = response_text
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
            prompt_text = ""
            try:
                prompt_text = build_prompt(review_obj)
            except Exception as e:  # noqa: BLE001 - prompt logging must never block
                logger.warning("Could not build AI prompt for logging: %s", e)
            try:
                ai = review_with_ai(review_obj, self.settings)
                # Persist exactly what we sent and what we got back (audit trail).
                self._persist_ai_io(ai_stem, prompt_text, ai.raw_text, ai, None)
                if ai.parsed_ok:
                    self.ai_review = ai
                    self.category = ai.verdict
                    if not override:  # a manual override still wins the impact level
                        impact_info["final_level"] = ai.impact_level
                    ai_reasons = list(ai.rationale)
                    if ai.summary:
                        ai_reasons.insert(0, ai.summary)
                    if ai.recommendations:
                        ai_reasons.append(
                            "Recommendations: " + "; ".join(ai.recommendations)
                        )
                    if ai_reasons:
                        impact_info["rationale"] = ai_reasons
                    used_ai = True
                else:
                    logger.warning("Bedrock reply not parseable; using deterministic verdict.")
            except Exception as e:  # noqa: BLE001 - never let AI break report generation
                logger.warning("Bedrock review unavailable (%s); using deterministic verdict.", e)
                self._persist_ai_io(ai_stem, prompt_text, "", None, str(e))

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

        generate_report(
            vpat_data=data,
            score_info=score_info,
            impact_info=impact_info,
            reviewer_answers=answers,
            output_path=str(out_path),
            logo_path=logo_path,
            settings=self.settings,
        )

        # Post-generation PDF validation (file exists, opens, all sections)
        self.after(0, lambda: self._set_progress(92, "Validating PDF…"))
        try:
            ok, problems = validate_report(str(out_path))
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
        self.after(0, lambda: self._set_progress(100, "Report generated successfully."))
        self.after(0, self._on_success)

    def _on_success(self):
        self._populate_summary()
        self.btn_save_as.config(state="normal")
        self._status(
            f"Done — verdict: {self.category}. Filed under "
            f"“{CATEGORY_FOLDER.get(self.category, '')}”.",
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


def main() -> None:
    """Launch the desktop GUI."""
    app = VPATReviewerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
