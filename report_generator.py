# SFBRN VPAT Reviewer — v10

A Windows desktop app that reads a vendor's VPAT document (PDF, Word, or
text) and produces a branded, professionally styled **VPAT Accessibility
Compliance — Summary Report** as a PDF. Everything runs on your own
computer: no internet, no accounts, no API keys, nothing leaves the machine.

This README is written for someone who is **learning to code**, so it
explains not just *what* each file is but *why* it exists.

---

## The big picture: how the app is put together

Think of the app as an assembly line with four stations. A file goes in one
end and a finished report comes out the other.

1. **`run_app.py` — the window you click on.** This is the graphical
   interface (built with Tkinter, Python's built-in windowing toolkit). It
   draws the buttons, the drag-and-drop area, the progress bar, and the
   Settings screen. It doesn't do any parsing or PDF work itself — it just
   collects your input and hands the job to the other files. Keeping the
   "screen" separate from the "brains" is a core habit in software: it means
   you can change how the app *looks* without risking the logic that makes it
   *correct*.

2. **`vpat_parser.py` — the reader.** It opens the vendor's document, pulls
   out the product name, dates, WCAG rows, statuses, and remarks, and
   calculates the compliance score. This file is the most battle-tested part
   of the project, so **we never edit it casually** (more on that below).

3. **`wcag_reference.py` — the dictionary.** For every WCAG criterion (like
   "1.4.3 Contrast (Minimum)") it stores the official description and a
   plain-language explanation. The report looks things up here so it never
   has to invent descriptions.

4. **`report_generator.py` — the writer.** It takes the parsed data and the
   dictionary and lays out the actual PDF: cover page, executive summary,
   barrier cards, tables, footer with page numbers, and so on. This is where
   all the colors, fonts, and layout rules live.

Two smaller helpers support the line:

- **`settings_manager.py`** remembers who is using the app (organization
  name, reviewer name, logo, threshold) in a small `settings.json` file, so
  the app isn't hard-wired to one person.
- **`test_v10_regression.py`** is an automated checklist that proves the
  math and layout still work every time you change something.

---

## Why this is a Python app and not the Electron/React stack in the brief

The project brief suggested building with Electron + React + a Python
backend, *"unless there is a strong technical reason to choose an equivalent
approach."* There is one, and it matters especially for someone learning:

- **One language, not four.** This app is Python end to end. The Electron
  route would mean juggling JavaScript, React, HTML/CSS, *and* Python at
  once — four things to learn and four things that can break.
- **It protects working code.** `vpat_parser.py` already contains many
  hard-won fixes for messy real-world VPATs (merged Word tables, weird date
  formats, vendor typos in status words). Rebuilding from scratch would throw
  that away and reintroduce bugs you already solved.
- **It still meets every requirement in the brief:** fully offline, no API
  keys, local-only storage, the Desktop folder structure, single-click
  install, SFBRN branding, all report sections, and PDF validation.

So the *goals* of the brief are met; only the underlying toolkit differs, for
good reasons.

---

## The one rule to remember

**Do not edit `vpat_parser.py` or `wcag_reference.py` without re-running the
tests.** These two files are "byte-for-byte" identical to the last known-good
version. Every fix inside `vpat_parser.py` is marked with a comment (for
example `# v9 FIX C`) so you can see *why* a line is the way it is before you
change it. If you ever do change them, run:

```
python -m pytest test_v10_regression.py -q
```

and make sure it still says `8 passed`.

---

## Files in this project

| File | Plain-English job |
|---|---|
| `run_app.py` | The clickable window (buttons, drag-drop, Settings, progress). |
| `vpat_parser.py` | Reads the VPAT and calculates the score. **Protected.** |
| `wcag_reference.py` | Official WCAG descriptions + plain-language text. **Protected.** |
| `report_generator.py` | Builds the styled PDF report. |
| `settings_manager.py` | Saves/loads who is using the app (`settings.json`). |
| `test_v10_regression.py` | Automated checks that guard the math and layout. |
| `make_demo.py` | Builds a sample report so you can see the output. |
| `requirements.txt` | The list of Python add-ons the app needs. |
| `build_exe.bat` | Turns the code into a Windows `.exe`. |
| `installer.iss` | Turns the `.exe` into a single-click installer. |
| `assets/` | Put `SFBRN_Logo.png` here (see the note inside). |
| `INSTALL_INSTRUCTIONS.txt` | Hand this to end users. |
| `BUILD_INSTRUCTIONS.md` | Step-by-step build guide for you. |

---

## How to run it right now (before packaging)

On your Windows machine, from inside this folder:

```
pip install -r requirements.txt
python run_app.py
```

The first time it opens, a short setup window asks for your organization and
name. After that, drag a VPAT onto the window and click **Generate Report**.

To see an example without a real VPAT, run `python make_demo.py` — it writes
a sample report you can open.

## How to turn it into an installer

See `BUILD_INSTRUCTIONS.md`. The short version: run `build_exe.bat`, then
open `installer.iss` in the free Inno Setup program and click Compile. You
get one file, `VPAT_Reviewer_Setup.exe`, to share.

---

## What "compliance score" means here

The score counts how many WCAG **Level AA** criteria the vendor fully
supports, divided by the Level AA criteria that actually apply, as a
percentage. Criteria the vendor marks **Not Applicable** are left out of that
math (a feature that doesn't exist can't pass or fail), but they still appear
in Section 2 as documented "known gaps" so nothing is hidden. This behavior
is deliberate and is locked in by the tests.
