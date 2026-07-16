"""Tkinter dialog for editing the grading policy.

This is a thin shell around the tested ``policy_form`` layer: it collects field
values and calls ``policy_form.from_form`` to build and validate a new
GradingPolicy, then persists it via ``config.settings.save_policy``. All rules
and validation live in ``policy_form`` (unit-tested); this file is only widgets.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from vpat_reviewer.config import policy_form, settings
from vpat_reviewer.domain.normalization import CANONICAL_STATUSES
from vpat_reviewer.domain.policy import GradingPolicy
from vpat_reviewer.ui.gui.widgets import make_scrollable, size_scrollable_dialog


class GradingPolicyDialog(tk.Toplevel):
    """Editor for score bands, threshold, graded level, and status classes."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Edit Grading Policy")
        self.resizable(True, True)
        self.transient(parent)  # type: ignore[arg-type]
        self.grab_set()
        self._policy = settings.load_policy()
        self._build()

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 3}

        # Pinned footer: pack first with side="bottom" so Save / Reset / Close are
        # never pushed off-screen by the fields above (which now scroll when the
        # dialog is taller than the screen, e.g. under display scaling or zoom).
        footer = tk.Frame(self)
        footer.pack(side="bottom", fill="x")
        btns = tk.Frame(footer)
        btns.pack(pady=10)
        tk.Button(btns, text="Save", command=self._save).pack(side="left", padx=6)
        tk.Button(btns, text="Reset to Defaults", command=self._reset).pack(side="left", padx=6)
        tk.Button(btns, text="Close", command=self.destroy).pack(side="left", padx=6)

        # Scrollable field area above the footer. Register the canvas in the main
        # window's wheel-scroll set so the mouse wheel scrolls it too.
        canvases = getattr(self._root(), "_canvases", set())
        canvas, body = make_scrollable(self, canvases, bg=str(self.cget("bg")))

        row = 0
        tk.Label(
            body,
            text="How VPATs are graded. Saved to settings and used by new reports.",
            wraplength=470,
            justify="left",
        ).grid(row=row, column=0, columnspan=3, **pad)
        row += 1

        tk.Label(body, text="WCAG level graded:").grid(row=row, column=0, sticky="e", **pad)
        self._level = tk.StringVar(value=self._policy.graded_level)
        tk.OptionMenu(body, self._level, "A", "AA").grid(row=row, column=1, sticky="w", **pad)
        row += 1

        tk.Label(body, text="Compliance threshold (%):").grid(row=row, column=0, sticky="e", **pad)
        self._threshold = tk.StringVar(value=str(self._policy.compliance_threshold))
        tk.Entry(body, textvariable=self._threshold, width=8).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        self._supported = self._status_checkboxes(
            body, row, "Count as a pass:", self._policy.supported_statuses
        )
        row += 1
        self._excluded = self._status_checkboxes(
            body, row, "Excluded from denominator:", self._policy.excluded_statuses
        )
        row += 1

        tk.Label(body, text="Score bands (min / label):").grid(row=row, column=0, sticky="ne", **pad)
        band_frame = tk.Frame(body)
        band_frame.grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        self._bands: list[tuple[tk.StringVar, tk.StringVar, str]] = []
        for b in self._policy.score_bands:
            fr = tk.Frame(band_frame)
            fr.pack(anchor="w", pady=1)
            mn = tk.StringVar(value=str(b.min_score))
            lbl = tk.StringVar(value=b.label)
            tk.Entry(fr, textvariable=mn, width=5).pack(side="left")
            tk.Entry(fr, textvariable=lbl, width=24).pack(side="left", padx=4)
            self._bands.append((mn, lbl, b.message))

        size_scrollable_dialog(self, canvas, body, footer)

    def _status_checkboxes(
        self, parent: tk.Misc, row: int, label: str, selected: tuple[str, ...]
    ) -> dict[str, tk.BooleanVar]:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="ne", padx=8, pady=3)
        frame = tk.Frame(parent)
        frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=8, pady=3)
        vars_: dict[str, tk.BooleanVar] = {}
        for status in CANONICAL_STATUSES:
            var = tk.BooleanVar(value=status in selected)
            tk.Checkbutton(frame, text=status, variable=var).pack(anchor="w")
            vars_[status] = var
        return vars_

    def _collect(self) -> dict[str, object]:
        return {
            "graded_level": self._level.get(),
            "compliance_threshold": self._threshold.get(),
            "supported_statuses": [s for s, v in self._supported.items() if v.get()],
            "excluded_statuses": [s for s, v in self._excluded.items() if v.get()],
            "bands": [
                {"min_score": mn.get(), "label": lbl.get(), "message": msg}
                for (mn, lbl, msg) in self._bands
            ],
        }

    def _save(self) -> None:
        policy, errors = policy_form.from_form(self._policy, self._collect())
        if errors or policy is None:
            messagebox.showerror("Invalid grading policy", "\n".join(errors), parent=self)
            return
        if settings.save_policy(policy):
            messagebox.showinfo(
                "Saved", "Grading policy saved. New reports will use it.", parent=self
            )
            self.destroy()
        else:
            messagebox.showerror("Save failed", "Could not write settings.json.", parent=self)

    def _reset(self) -> None:
        if messagebox.askyesno(
            "Reset grading policy", "Reset all grading settings to defaults?", parent=self
        ):
            settings.save_policy(GradingPolicy.default())
            self.destroy()
