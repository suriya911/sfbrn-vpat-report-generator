"""Shared Tkinter helpers for the desktop GUI (adapter layer).

These are the pieces that make the UI fit any screen and any Windows
display-scaling setting. They live in their own module so both the main window
(``app.py``) and the pop-up dialogs (``policy_dialog.py``) can use them without
importing each other:

- ``work_area`` — the usable desktop rectangle (screen minus the taskbar), so a
  window can be sized and centred to always fit.
- ``make_scrollable`` — a vertically scrollable region with an auto-hiding
  scrollbar, so content taller than its window scrolls instead of being clipped.
- ``size_scrollable_dialog`` — sizes a scrollable dialog to its content but never
  taller than the work area, so its pinned buttons are never pushed off-screen.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk


def work_area(widget: tk.Misc, margin: int = 48) -> tuple[int, int, int, int]:
    """``(left, top, width, height)`` of the usable desktop — the primary
    monitor minus the taskbar.

    Falls back to the full screen minus ``margin`` when the Windows API isn't
    available (non-Windows, or the call fails), so the caller always gets a
    workable rectangle.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030 — the primary monitor's taskbar-excluded rect,
            # in physical pixels, with left/top for correct multi-monitor centring.
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        except (AttributeError, OSError):
            pass
    return (0, 0, widget.winfo_screenwidth() - margin, widget.winfo_screenheight() - margin)


def make_scrollable(
    parent: tk.Misc, canvases: set[tk.Canvas], bg: str
) -> tuple[tk.Canvas, tk.Frame]:
    """A vertically scrollable region: returns ``(canvas, inner_frame)``.

    Pack content into ``inner_frame``. The scrollbar auto-hides — it appears only
    when the content is taller than the viewport, so a region that fits shows no
    scrollbar and looks unchanged. The canvas is added to ``canvases`` so a shared
    ``<MouseWheel>`` handler can find and scroll whichever region the pointer is
    over, and it removes itself from that set when destroyed.
    """
    canvas = tk.Canvas(parent, bg=bg, highlightthickness=0)
    vsb = ttk.Scrollbar(
        parent, orient="vertical", command=canvas.yview, style="Slim.Vertical.TScrollbar"
    )
    canvas.pack(side="left", fill="both", expand=True)

    def _autohide(first: str, last: str) -> None:
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
    canvases.add(canvas)

    def _forget(event: tk.Event) -> None:
        # Drop the destroyed canvas from the shared set so the wheel handler
        # never tries to scroll a dead widget. Guard on the canvas itself —
        # <Destroy> also fires for descendants via bindtags.
        if event.widget is canvas:
            canvases.discard(canvas)

    canvas.bind("<Destroy>", _forget, add="+")
    return canvas, inner


def size_scrollable_dialog(
    win: tk.Toplevel,
    canvas: tk.Canvas,
    inner: tk.Frame,
    bottom: tk.Widget,
    max_frac: float = 0.9,
    scrollbar_pad: int = 22,
) -> None:
    """Give a scrollable dialog a sensible initial size, then centre it.

    The dialog is made as tall as its content (``inner``) plus its pinned button
    row (``bottom``), but capped to ``max_frac`` of the work area — so tall
    content scrolls inside the canvas instead of overflowing the screen and
    hiding the buttons. Call once, after the dialog's widgets are built.
    """
    try:
        win.update_idletasks()
        left, top, area_w, area_h = work_area(win)
        btn_h = bottom.winfo_reqheight()
        cap_h = int(area_h * max_frac) - btn_h - 8
        canvas.configure(
            width=min(inner.winfo_reqwidth() + scrollbar_pad, int(area_w * max_frac)),
            height=max(120, min(inner.winfo_reqheight(), cap_h)),
        )
        win.update_idletasks()
        w = min(win.winfo_reqwidth(), area_w)
        h = min(win.winfo_reqheight(), area_h)
        x = left + max(0, (area_w - w) // 2)
        y = top + max(0, (area_h - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.minsize(min(360, area_w), min(240, area_h))
    except tk.TclError:
        # Never let sizing math stop the dialog from opening; a floor keeps it usable.
        win.minsize(360, 240)
