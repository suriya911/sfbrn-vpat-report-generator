"""
SFBRN VPAT Reviewer — Desktop Application
Python + Tkinter GUI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import shutil
import logging
from datetime import date
from pathlib import Path
import subprocess
from vpat_parser import parse_vpat, get_aa_barriers, compliance_score, calculate_impact
from report_generator import generate_report, validate_report
import settings_manager

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Colours ────────────────────────────────────────────────────────────────────
BG_APP     = "#f0f4f8"
BG_CARD    = "#ffffff"
BG_HEADER  = "#1e3a5f"
BG_SECTION = "#eef4fb"
FG_NAVY    = "#1e3a5f"
FG_BLUE    = "#2d6a9f"
FG_BODY    = "#1a1a2e"
FG_CAPTION = "#555577"
FG_WHITE   = "#ffffff"
C_BORDER   = "#b8d4ee"
C_GREEN    = "#1a6e3c"
C_ORANGE   = "#a05c00"
C_RED      = "#9b2335"
C_SUCCESS  = "#1a6e3c"
C_BTN_PRI  = "#1e3a5f"
C_BTN_HOV  = "#2d6a9f"

IMPACT_COLORS = {"High": C_RED, "Medium": C_ORANGE, "Low": C_GREEN}


# ── Folder helpers ─────────────────────────────────────────────────────────────

def _desktop() -> Path:
    return Path.home() / "Desktop"

def _ensure_folders() -> tuple:
    base    = _desktop() / "VPAT Reviewer Files"
    vpats   = base / "VPATs"
    reports = base / "VPAT Summary Reports"
    for d in (base, vpats, reports):
        d.mkdir(parents=True, exist_ok=True)
    return vpats, reports

def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()

def _next_report_path(reports_dir: Path, product: str) -> Path:
    today = date.today().strftime("%Y-%m-%d")
    # Truncate to 50 chars to prevent Windows MAX_PATH issues
    safe  = (_safe_filename(product) or "Product")[:50].strip()
    base  = f"{safe}_VPAT_Summary_Report_{today}"
    path  = reports_dir / f"{base}.pdf"
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
        intro = ("Welcome! Answer a few questions so your reports show the "
                 "right organization and reviewer. You can change these any "
                 "time from the Settings button."
                 if first_run else
                 "Update the reviewer and organization details used on "
                 "generated reports.")
        tk.Label(self, text=intro, font=("Segoe UI", 9), bg=BG_CARD,
                 fg=FG_CAPTION, wraplength=420, justify="left").grid(
                     row=0, column=0, columnspan=2, padx=16, pady=(14, 8),
                     sticky="w")

        self._vars = {}
        row = 1
        for key, label in settings_manager.FIELD_LABELS:
            tk.Label(self, text=label + ":", font=("Segoe UI", 9, "bold"),
                     bg=BG_CARD, fg=FG_NAVY).grid(
                         row=row, column=0, padx=(16, 6), pady=4, sticky="e")
            var = tk.StringVar(value=str(current.get(key, "")))
            tk.Entry(self, textvariable=var, font=("Segoe UI", 9),
                     width=38).grid(row=row, column=1, padx=(0, 16), pady=4,
                                    sticky="w")
            self._vars[key] = var
            row += 1

        # Optional custom logo
        tk.Label(self, text="Custom logo (optional):",
                 font=("Segoe UI", 9, "bold"), bg=BG_CARD, fg=FG_NAVY).grid(
                     row=row, column=0, padx=(16, 6), pady=4, sticky="e")
        logo_row = tk.Frame(self, bg=BG_CARD)
        logo_row.grid(row=row, column=1, padx=(0, 16), pady=4, sticky="w")
        self._vars["logo_path"] = tk.StringVar(
            value=str(current.get("logo_path", "")))
        tk.Entry(logo_row, textvariable=self._vars["logo_path"],
                 font=("Segoe UI", 8), width=28).pack(side="left")
        tk.Button(logo_row, text="Browse…", font=("Segoe UI", 8),
                  command=self._browse_logo, cursor="hand2").pack(
                      side="left", padx=4)
        row += 1
        tk.Label(self, text="Leave logo blank to use the bundled default.",
                 font=("Segoe UI", 8), bg=BG_CARD, fg=FG_CAPTION).grid(
                     row=row, column=1, padx=(0, 16), sticky="w")
        row += 1

        btn_row = tk.Frame(self, bg=BG_CARD)
        btn_row.grid(row=row, column=0, columnspan=2, pady=(12, 14))
        tk.Button(btn_row, text="Save Settings", font=("Segoe UI", 9, "bold"),
                  bg=C_BTN_PRI, fg=FG_WHITE, relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._save).pack(side="left", padx=6)
        if not first_run:
            tk.Button(btn_row, text="Cancel", font=("Segoe UI", 9),
                      bg=BG_SECTION, fg=FG_NAVY, relief="flat", padx=16,
                      pady=6, cursor="hand2",
                      command=self.destroy).pack(side="left", padx=6)

    def _browse_logo(self):
        path = filedialog.askopenfilename(
            title="Choose logo image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif"),
                       ("All files", "*.*")])
        if path:
            self._vars["logo_path"].set(path)

    def _save(self):
        values = {k: v.get().strip() for k, v in self._vars.items()}
        if not values.get("org_name") or not values.get("reviewer_name"):
            messagebox.showwarning(
                "Missing Information",
                "Organization name and reviewer name are required.",
                parent=self)
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
                parent=self)


# ── Main application ───────────────────────────────────────────────────────────

class VPATReviewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SFBRN VPAT Reviewer")
        self.geometry("860x780")
        self.minsize(740, 640)
        self.configure(bg=BG_APP)
        self.resizable(True, True)

        # State
        self.vpat_path    = tk.StringVar(value="")
        self.vpat_data    = None
        self.score_info   = {}
        self.impact_info  = {}
        self.report_path  = None
        self._processing  = False

        # Reviewer question variables
        self.var_audience  = tk.StringVar(value="campus_wide")
        self.var_access    = tk.StringVar(value="limits_some")
        self.var_legal     = tk.StringVar(value="medium")
        self.var_deploy    = tk.StringVar(value="department")
        self.var_override  = tk.StringVar(value="")   # empty = use suggested

        # Load reviewer/organization settings (first run shows setup dialog)
        first_run = settings_manager.is_first_run()
        self.settings = settings_manager.load_settings()

        self._build_ui()
        self._ensure_dirs()

        if first_run:
            self.after(200, self._first_run_setup)

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
            self._status("Settings saved. New reports will use the "
                         "updated details.", C_SUCCESS)

    def _refresh_identity(self):
        short = self.settings.get("org_short") or "VPAT"
        self.title(f"{short} VPAT Reviewer")
        if hasattr(self, "lbl_org_badge"):
            self.lbl_org_badge.config(text=short)

    def _ensure_dirs(self):
        try:
            self.vpats_dir, self.reports_dir = _ensure_folders()
        except Exception as e:
            messagebox.showerror("Folder Error",
                f"Could not create Desktop folders:\n{e}\n\n"
                "Reports will be saved to the current directory.")
            self.vpats_dir   = Path(".")
            self.reports_dir = Path(".")

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_body()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_HEADER, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self.lbl_org_badge = tk.Label(
            hdr, text=self.settings.get("org_short", "SFBRN"),
            font=("Segoe UI", 18, "bold"), bg=BG_HEADER, fg=FG_WHITE)
        self.lbl_org_badge.pack(side="left", padx=16, pady=12)

        tk.Label(hdr, text="VPAT Accessibility Compliance Reviewer",
                 font=("Segoe UI", 11), bg=BG_HEADER, fg="#aacce8").pack(
                     side="left", padx=4, pady=12)

        # Settings + open folder buttons
        tk.Button(hdr, text="\u2699 Settings",
                  font=("Segoe UI", 8), bg="#2d6a9f", fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._open_settings).pack(side="right", padx=4, pady=14)
        tk.Button(hdr, text="Open VPATs Folder",
                  font=("Segoe UI", 8), bg="#2d6a9f", fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._open_vpats_folder).pack(side="right", padx=4, pady=14)
        tk.Button(hdr, text="Open Reports Folder",
                  font=("Segoe UI", 8), bg="#2d6a9f", fg=FG_WHITE,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._open_reports_folder).pack(side="right", padx=4, pady=14)

    def _build_body(self):
        # Scrollable main container
        canvas = tk.Canvas(self, bg=BG_APP, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.body = tk.Frame(canvas, bg=BG_APP)
        self._canvas_window = canvas.create_window((0,0), window=self.body, anchor="nw")

        def _on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_resize(e):
            canvas.itemconfig(self._canvas_window, width=e.width)

        self.body.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        pad = {"padx": 18, "pady": 8}

        # ── Upload section ─────────────────────────────────────────────────────
        self._card(self.body, "1  Upload VPAT Document", self._build_upload_card).pack(
            fill="x", **pad)

        # ── Questions section ──────────────────────────────────────────────────
        self._card(self.body, "2  Impact Assessment Questions", self._build_questions_card).pack(
            fill="x", **pad)

        # ── Generate section ───────────────────────────────────────────────────
        self._card(self.body, "3  Generate Report", self._build_generate_card).pack(
            fill="x", **pad)

        # ── Results section (hidden until report generated) ────────────────────
        self.results_frame = self._card(self.body, "4  Results", self._build_results_card)
        self.results_frame.pack(fill="x", **pad)
        self.results_frame.pack_forget()  # hidden initially

    def _card(self, parent, title: str, builder_fn) -> tk.Frame:
        """Create a white card with a title bar."""
        outer = tk.Frame(parent, bg=BG_APP)

        # Title bar
        title_bar = tk.Frame(outer, bg=FG_NAVY, height=32)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text=title, font=("Segoe UI", 9, "bold"),
                 bg=FG_NAVY, fg=FG_WHITE).pack(side="left", padx=12, pady=6)

        # Content area
        content = tk.Frame(outer, bg=BG_CARD, bd=0,
                           highlightbackground=C_BORDER, highlightthickness=1)
        content.pack(fill="x")
        builder_fn(content)
        return outer

    # ── Upload card ────────────────────────────────────────────────────────────

    def _build_upload_card(self, parent):
        # Drop zone
        drop = tk.Frame(parent, bg=BG_SECTION, height=80,
                        highlightbackground=C_BORDER, highlightthickness=1)
        drop.pack(fill="x", padx=16, pady=(12,6))
        drop.pack_propagate(False)

        self.lbl_drop = tk.Label(drop,
            text="Drag and drop a VPAT here, or click the button below",
            font=("Segoe UI", 10), bg=BG_SECTION, fg=FG_CAPTION)
        self.lbl_drop.pack(expand=True)

        btn_row = tk.Frame(parent, bg=BG_CARD)
        btn_row.pack(fill="x", padx=16, pady=(0,12))

        self._pri_btn(btn_row, "Upload VPAT (PDF / Word / TXT)",
                      self._browse_vpat).pack(side="left", padx=(0,8))

        self.lbl_file = tk.Label(btn_row, text="No file selected",
            font=("Segoe UI", 9), bg=BG_CARD, fg=FG_CAPTION)
        self.lbl_file.pack(side="left", pady=4)

    # ── Questions card ─────────────────────────────────────────────────────────

    def _build_questions_card(self, parent):
        pad = {"padx": 20, "pady": 5}

        questions = [
            ("How many users will this product serve?", "var_audience", [
                ("1 user — individual use",   "individual"),
                ("2–20 users — small team",   "small_team"),
                ("21+ users — campus-wide",   "campus_wide"),
            ]),
            ("How does this product affect access for users with disabilities?", "var_access", [
                ("Does not limit access",      "no_limit"),
                ("Limits some access",         "limits_some"),
                ("Denies access to features",  "denies_access"),
            ]),
            ("What is the legal exposure level for this product?", "var_legal", [
                ("Low — minimal ADA/504 risk",    "low"),
                ("Medium — moderate risk",        "medium"),
                ("High — significant ADA/504 risk","high"),
            ]),
            ("What is the deployment scope?", "var_deploy", [
                ("Individual",    "individual"),
                ("Department",    "department"),
                ("Campus-wide",   "campus_wide"),
            ]),
        ]

        for q_text, var_name, options in questions:
            tk.Label(parent, text=q_text, font=("Segoe UI", 9, "bold"),
                     bg=BG_CARD, fg=FG_NAVY, wraplength=700, justify="left").pack(
                         anchor="w", **pad)
            radio_row = tk.Frame(parent, bg=BG_CARD)
            radio_row.pack(anchor="w", padx=20, pady=(0,8))
            var = getattr(self, var_name)
            for label, value in options:
                tk.Radiobutton(radio_row, text=label, variable=var, value=value,
                    font=("Segoe UI", 9), bg=BG_CARD, fg=FG_BODY,
                    activebackground=BG_CARD, selectcolor=BG_SECTION,
                    cursor="hand2").pack(side="left", padx=8)

        # Divider
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x", padx=20, pady=4)

        # Override row
        override_row = tk.Frame(parent, bg=BG_CARD)
        override_row.pack(fill="x", padx=20, pady=(4,12))
        tk.Label(override_row, text="Override suggested impact level (optional):",
                 font=("Segoe UI", 9, "bold"), bg=BG_CARD, fg=FG_NAVY).pack(side="left")
        for label, value in [("Use suggested", ""), ("Low", "Low"),
                              ("Medium", "Medium"), ("High", "High")]:
            tk.Radiobutton(override_row, text=label,
                variable=self.var_override, value=value,
                font=("Segoe UI", 9), bg=BG_CARD, fg=FG_BODY,
                activebackground=BG_CARD, selectcolor=BG_SECTION,
                cursor="hand2").pack(side="left", padx=8)

    # ── Generate card ──────────────────────────────────────────────────────────

    def _build_generate_card(self, parent):
        btn_row = tk.Frame(parent, bg=BG_CARD)
        btn_row.pack(fill="x", padx=16, pady=12)

        self.btn_generate = self._pri_btn(btn_row, "Generate Report",
                                          self._start_generate, state="disabled")
        self.btn_generate.pack(side="left", padx=(0,8))

        self.btn_save_as = tk.Button(btn_row, text="Save Report As…",
            font=("Segoe UI", 9), bg="#e8f0fb", fg=FG_NAVY,
            relief="flat", padx=12, pady=6, cursor="hand2",
            state="disabled", command=self._save_as)
        self.btn_save_as.pack(side="left", padx=(0,8))

        # Progress
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(parent, variable=self.progress_var,
                                        maximum=100, length=400, mode="determinate")
        self.progress.pack(padx=16, pady=(0,6), fill="x")

        self.lbl_status = tk.Label(parent, text="Ready — upload a VPAT to begin.",
            font=("Segoe UI", 9), bg=BG_CARD, fg=FG_CAPTION)
        self.lbl_status.pack(anchor="w", padx=18, pady=(0,10))

    # ── Results card ───────────────────────────────────────────────────────────

    def _build_results_card(self, parent):
        self.results_content = tk.Frame(parent, bg=BG_CARD)
        self.results_content.pack(fill="x", padx=16, pady=12)

    def _populate_results(self):
        # Clear old
        for w in self.results_content.winfo_children():
            w.destroy()

        data = self.vpat_data
        score = self.score_info.get("score")
        level = self.impact_info.get("final_level",
                    self.impact_info.get("suggested_level", "Medium"))

        # Score + impact badge row
        badge_row = tk.Frame(self.results_content, bg=BG_CARD)
        badge_row.pack(fill="x", pady=(0,10))

        # Compliance score badge
        score_str = f"{score}%" if score is not None else "N/A"
        score_color = C_GREEN if (score or 0) >= 75 else (C_ORANGE if (score or 0) >= 50 else C_RED)
        score_frame = tk.Frame(badge_row, bg=score_color)
        score_frame.pack(side="left", padx=(0,10))
        tk.Label(score_frame, text="Compliance Score",
                 font=("Segoe UI", 8), bg=score_color, fg=FG_WHITE).pack(padx=12, pady=(6,0))
        tk.Label(score_frame, text=score_str,
                 font=("Segoe UI", 20, "bold"), bg=score_color, fg=FG_WHITE).pack(padx=12, pady=(0,6))

        # Impact badge
        impact_color = IMPACT_COLORS.get(level, C_ORANGE)
        impact_frame = tk.Frame(badge_row, bg=impact_color)
        impact_frame.pack(side="left")
        tk.Label(impact_frame, text="Impact Level",
                 font=("Segoe UI", 8), bg=impact_color, fg=FG_WHITE).pack(padx=12, pady=(6,0))
        tk.Label(impact_frame, text=level.upper(),
                 font=("Segoe UI", 20, "bold"), bg=impact_color, fg=FG_WHITE).pack(padx=12, pady=(0,6))

        # Summary info
        info_frame = tk.Frame(self.results_content, bg=BG_SECTION,
                              highlightbackground=C_BORDER, highlightthickness=1)
        info_frame.pack(fill="x", pady=(0,8))

        # Barriers exclude Not Applicable (feature absent = no barrier)
        aa_barriers = [c for c in data.criteria if c.level == "AA" and c.normalized_status not in ("Supports", "Not Applicable")]

        rows = [
            ("Product",          data.product_name or "—"),
            ("Vendor",           data.vendor_name or "—"),
            ("Vendor Report Date", data.vendor_report_date_raw or "—"),
            ("Level AA Barriers", str(len(aa_barriers))),
            ("Score Message",    self.score_info.get("message","")[:120]),
            ("Report Saved To",  str(self.report_path) if self.report_path else "—"),
        ]
        for label, value in rows:
            row = tk.Frame(info_frame, bg=BG_SECTION)
            row.pack(fill="x")
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 8, "bold"),
                     bg=BG_SECTION, fg=FG_NAVY, width=22, anchor="e").pack(side="left", padx=6, pady=2)
            tk.Label(row, text=value, font=("Segoe UI", 8),
                     bg=BG_SECTION, fg=FG_BODY, anchor="w", wraplength=520).pack(
                         side="left", padx=4)

        # High impact notice
        if level == "High":
            notice = tk.Frame(self.results_content, bg="#fdf0f0",
                              highlightbackground="#e04040", highlightthickness=1)
            notice.pack(fill="x", pady=(4,0))
            tk.Label(notice,
                text="HIGH IMPACT — An Alternative Access Plan is required before campus-wide deployment.",
                font=("Segoe UI", 9, "bold"), bg="#fdf0f0", fg=C_RED,
                wraplength=720, justify="left").pack(padx=12, pady=8, anchor="w")

        # Open report button
        if self.report_path and Path(self.report_path).exists():
            self._pri_btn(self.results_content, "Open Report PDF",
                          lambda: os.startfile(str(self.report_path))
                          if os.name == "nt" else None).pack(
                              side="left", pady=(8,0))

        # Show the results card
        self.results_frame.pack(fill="x", padx=18, pady=8)

    # ── Button helpers ─────────────────────────────────────────────────────────

    def _pri_btn(self, parent, text, command, state="normal"):
        btn = tk.Button(parent, text=text,
            font=("Segoe UI", 9, "bold"), bg=C_BTN_PRI, fg=FG_WHITE,
            relief="flat", padx=14, pady=7, cursor="hand2",
            state=state, command=command,
            activebackground=C_BTN_HOV, activeforeground=FG_WHITE)
        btn.bind("<Enter>", lambda e: btn.configure(bg=C_BTN_HOV) if str(btn["state"]) != "disabled" else None)
        btn.bind("<Leave>", lambda e: btn.configure(bg=C_BTN_PRI) if str(btn["state"]) != "disabled" else None)
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
            ]
        )
        if path:
            self._load_vpat(path)

    def _load_vpat(self, path: str):
        self.vpat_path.set(path)
        fname = Path(path).name
        ext   = Path(path).suffix.upper().lstrip(".")
        self.lbl_file.config(
            text=f"{fname}  [{ext}]",
            fg=FG_NAVY, font=("Segoe UI", 9, "bold"))
        self.lbl_drop.config(text=f"Loaded: {fname}")
        self.btn_generate.config(state="normal", bg=C_BTN_PRI)
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
            "audience":      self.var_audience.get(),
            "access_impact": self.var_access.get(),
            "legal_exposure": self.var_legal.get(),
            "deployment":    self.var_deploy.get(),
        }
        barriers = get_aa_barriers(data)
        impact_info = calculate_impact(answers, barriers, score_info)

        # Apply override
        override = self.var_override.get()
        if override:
            impact_info["final_level"] = override
            impact_info["rationale"].insert(0,
                f"Reviewer manually overrode suggested impact level to: {override}.")
        else:
            impact_info["final_level"] = impact_info["suggested_level"]

        self.impact_info = impact_info

        self.after(0, lambda: self._set_progress(65, "Building PDF report…"))

        # Copy VPAT to local folder
        try:
            today = date.today().strftime("%Y-%m-%d")
            safe  = "".join(c if c.isalnum() or c in "-_ " else "_"
                            for c in (data.product_name or "Product")).strip()
            ext   = Path(path).suffix
            dest  = self.vpats_dir / f"{safe}_{today}{ext}"
            if not dest.exists():
                shutil.copy2(path, dest)
        except Exception as e:
            logger.warning(f"Could not copy VPAT: {e}")

        # Determine output path
        product = data.product_name or "Product"
        out_path = _next_report_path(self.reports_dir, product)

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
        self.after(0, lambda: self._set_progress(92, "Validating PDF\u2026"))
        try:
            ok, problems = validate_report(str(out_path))
            if not ok:
                logger.error("PDF validation problems: %s", problems)
                self.after(0, lambda: messagebox.showwarning(
                    "Report Validation",
                    "The report was generated but validation flagged:\n\u2022 "
                    + "\n\u2022 ".join(problems[:6])))
        except Exception as e:
            logger.warning("PDF validation could not run: %s", e)

        self.report_path = out_path
        self.after(0, lambda: self._set_progress(100, "Report generated successfully."))
        self.after(0, self._on_success)

    def _on_success(self):
        self._populate_results()
        self.btn_save_as.config(state="normal")
        score = self.score_info.get("score")
        level = self.impact_info.get("final_level", "Medium")
        msg   = self.score_info.get("message", "")
        messagebox.showinfo(
            "Report Generated",
            f"Report saved to:\n{self.report_path}\n\n"
            f"Compliance Score: {score}%\n"
            f"Impact Level: {level}\n\n"
            f"{msg}"
        )

    def _on_error(self, msg: str):
        self._status(f"Error: {msg}", color=C_RED)
        self.progress_var.set(0)
        messagebox.showerror("Processing Error",
            f"An error occurred during report generation:\n\n{msg}\n\n"
            "Please check that the file is a valid VPAT document and try again.")

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

    def _open_vpats_folder(self):
        try:
            if os.name == "nt":
                os.startfile(str(self.vpats_dir))
            else:
                subprocess.Popen(["xdg-open", str(self.vpats_dir)])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_reports_folder(self):
        try:
            if os.name == "nt":
                os.startfile(str(self.reports_dir))
            else:
                subprocess.Popen(["xdg-open", str(self.reports_dir)])
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VPATReviewerApp()
    app.mainloop()
