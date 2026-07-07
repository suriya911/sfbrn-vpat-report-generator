# VPAT Reviewer v10 — Build & Release Guide

This guide is for you (the maintainer), not end users. End users only ever
see `VPAT_Reviewer_Setup.exe` and `INSTALL_INSTRUCTIONS.txt`.

## What changed in v10

1. **Sample-format visual redesign** of `report_generator.py`:
   running header (4pt blue top border, logo block, title, date), three-part
   footer with true "Page X of Y" (two-pass NumberedCanvas), Executive
   Summary compliance meter with progress bar and threshold language,
   accent-bar callout boxes, redesigned barrier cards (italic quoted WCAG
   criterion text → "What this means" → pill badges → shaded Vendor Remarks),
   and four-column reference tables with pill badges. Only the approved
   palette is used (`#1a4f8a`, `#2e6db5`, `#e8f0fb`, `#b5d4f4`, plus the five
   status badge colors).
2. **Option A scoring policy** (deliberate decision — do not regress):
   v9 scoring is preserved (Not Applicable excluded from the denominator AND
   the barrier count), but NA criteria now *appear* in Section 2 as
   transparently documented known gaps, like the sample report. The scope
   callout explains this to readers.
3. **Settings system** (`settings_manager.py` + Settings dialog in
   `run_app.py`): organization name/short name, reviewer name/title, contact,
   threshold, and optional custom logo are stored in a local `settings.json`.
   First launch shows a setup dialog, so anyone can use the app — not just
   SFBRN. Defaults remain SFBRN / Jonathan Hale.
4. **Post-generation PDF validation** (`validate_report`): file exists,
   non-zero, opens, all required sections present, score present. The app
   warns if validation flags anything.
5. **Packaging workflow**: `build_exe.bat` (PyInstaller) + `installer.iss`
   (Inno Setup) produce a single-click installer that creates the Desktop
   folder structure and shortcuts with no technical questions.

**Unchanged on purpose:** `vpat_parser.py` and `wcag_reference.py` are
byte-identical to v9 — every hard-won parser fix (merged DOCX tables, date
handling, status-normalization order, 602.3 orphan gating, vendor scan
window) is untouched.

## Architecture note

The master prompt suggested Electron + React + FastAPI "unless there is a
strong technical reason to choose an equivalent approach." We kept the
Python/Tkinter/ReportLab architecture deliberately: it preserves the
regression-tested v9 parser, keeps the whole app in one language you are
learning, and still satisfies every functional requirement (offline, no API
keys, local storage, Desktop folders, single-click install, SFBRN branding,
PDF validation).

## Files in this release

| File | Role | Changed in v10? |
|---|---|---|
| `run_app.py` | Tkinter GUI, pipeline, folders, naming | Yes (settings, validation) |
| `report_generator.py` | ReportLab PDF engine | Yes (full visual redesign) |
| `vpat_parser.py` | Parsing, scoring, impact | **No — do not touch** |
| `wcag_reference.py` | WCAG 2.1 descriptions + plain language | No |
| `settings_manager.py` | settings.json load/save | New |
| `test_v10_regression.py` | pytest regression suite | New |
| `build_exe.bat` | PyInstaller build | New |
| `installer.iss` | Inno Setup installer | New |
| `requirements.txt` | dependencies | New |
| `INSTALL_INSTRUCTIONS.txt` | end-user install guide | New |

## Build steps (on your Windows machine)

1. **Copy the v10 files** into your `vpat_app\` source folder, replacing the
   old `run_app.py` and `report_generator.py` and adding the new files.
   Keep your existing `assets\SFBRN_Logo.png` where it is.
2. **Run the regression tests first** (always, before any release):
   ```
   cd vpat_app
   pip install -r requirements.txt
   python -m pytest test_v10_regression.py -q
   ```
   All 8 tests must pass. They protect the CCPS 57% / Minitab 91% anchors,
   the NA-exclusion scoring rule, status-normalization order, Option A
   display behavior, and custom-settings identity. Also re-run your original
   CCPS PDF and Minitab DOCX files through the app and confirm 57% / 91%.
3. **Build the .exe**: double-click `build_exe.bat`. It installs
   requirements, runs PyInstaller, and copies the logo. Output lands in
   `dist\VPAT_Reviewer\`.
4. **Build the installer**: install Inno Setup (free, jrsoftware.org) if you
   don't have it, open `installer.iss`, press **Build → Compile**. Output:
   `Output\VPAT_Reviewer_Setup.exe` — that single file is what you give to
   other users, along with `INSTALL_INSTRUCTIONS.txt`.
5. **Smoke-test the installer** on a clean profile: install, confirm the
   Desktop folders and shortcut appear, complete the first-run setup dialog,
   generate a report from a known VPAT, and confirm the PDF lands in
   `Desktop\VPAT Reviewer Files\VPAT Summary Reports\`.

## Release checklist

- [ ] `pytest test_v10_regression.py` → 8 passed
- [ ] CCPS PDF through the app → 57%, 3 barriers (1.4.3, 1.4.4, 2.4.7)
- [ ] Minitab DOCX through the app → 91%, 1 barrier (3.3.4)
- [ ] Report visually matches the approved sample (header, footer, meter,
      cards, tables)
- [ ] First-run setup dialog appears on a machine with no `settings.json`
- [ ] Installer creates both Desktop subfolders
- [ ] App runs with the network disabled
