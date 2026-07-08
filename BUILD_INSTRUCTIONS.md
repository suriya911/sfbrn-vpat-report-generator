# VPAT Reviewer — Build & Release Guide

This guide is for the maintainer, not end users. End users only ever see
`VPAT_Reviewer.exe` (or the `VPAT_Reviewer_Setup.exe` installer) and
`INSTALL_INSTRUCTIONS.txt`.

> Architecture, where code lives, and how to extend the app safely are
> documented separately in **`CLAUDE.md`** and **`docs/`**. Read those before
> changing code. This file is only about producing a shippable build.

## What you produce

| Artifact | How | Who gets it |
|---|---|---|
| `dist/VPAT_Reviewer.exe` | `build_exe.bat` | The whole team — a single, self-contained file. No Python needed on their machine. |
| `Output/VPAT_Reviewer_Setup.exe` | Inno Setup on `installer.iss` | Users who want a "real" install (Desktop folders + shortcut). Optional. |

The `.exe` is a **onefile** PyInstaller build: everything (Python runtime,
reportlab/pdfplumber/python-docx/pypdf, and `wcag.json`) is packed into one
file. On first run it writes a `settings.json` **next to itself**, so keep the
exe somewhere writable (Desktop, a user folder — not `C:\Program Files`). The
Inno installer handles this correctly by installing to LocalAppData.

## Prerequisites (one time)

- **Python 3.10+** on your PATH (`python --version`).
- For the optional installer: **Inno Setup** (free, https://jrsoftware.org).

Everything else (`pyinstaller`, the app's own dependencies) is installed for you
by `build_exe.bat` via `pip install -e ".[build]"`.

## Build steps

1. **Run the tests first — always, before any release.** From the `rebuild`
   folder:
   ```
   pip install -e ".[dev]"
   python -m pytest -q
   ```
   All tests must pass. They protect the scoring rules (Option A / NA excluded),
   status normalization, the parser fixes, the WCAG dataset completeness, and
   the editable grading policy. Also confirm the behavior anchor:
   ```
   python make_demo.py
   ```
   must print `Score: 72 | ... | Validation: OK`.

2. **Build the single .exe:** double-click `build_exe.bat` (or run it from a
   terminal). Output lands at `dist\VPAT_Reviewer.exe`. This one file is what
   you share with the team.

3. **Smoke-test the .exe** on a machine (or clean user profile) *without* a dev
   environment:
   - Double-click it — the GUI opens, and on a machine with no `settings.json`
     the first-run setup dialog appears.
   - Generate a report from a known VPAT and confirm the PDF is produced.
   - Confirm it runs with networking disabled (the app is fully offline).

4. **(Optional) Build the click-through installer:** open `installer.iss` in
   Inno Setup, press **Build → Compile**. Output:
   `Output\VPAT_Reviewer_Setup.exe`. Give users that single file plus
   `INSTALL_INSTRUCTIONS.txt`. It installs to LocalAppData (no admin rights),
   creates the Desktop folder structure, and adds a shortcut.

## How the packaging works (so you can fix it)

- **`vpat_reviewer.spec`** is the PyInstaller recipe. It does two things that a
  bare `pyinstaller run_app.py` cannot:
  1. Bundles `src/vpat_reviewer/reference/data/wcag.json` at its package path so
     the frozen app's `importlib.resources` call still finds it.
  2. Pulls in the dynamically-imported submodules of reportlab / pdfplumber /
     pdfminer / pypdf / python-docx via `collect_submodules`.
- **`run_app.py`** is the entry point PyInstaller freezes; it just calls
  `vpat_reviewer.ui.gui.app:main`.
- **Adding a data file?** Add it to `datas` in the spec.
- **Runtime `ModuleNotFoundError` after building?** Add
  `collect_submodules("<pkg>")` to `hiddenimports` in the spec.
- The frozen app detects itself via `sys.frozen` and writes `settings.json`
  next to the executable — see `config/settings.py::default_settings_path`.

## Versioning

- App version lives in `pyproject.toml` (`version = "11.0.0"`) and is mirrored
  in `installer.iss` (`AppVersion`). Bump both together on a release.

## Release checklist

- [ ] `python -m pytest -q` → all green
- [ ] `python make_demo.py` → `Score: 72 | ... | Validation: OK`
- [ ] `ruff check .` and `mypy` → clean
- [ ] `build_exe.bat` → `dist\VPAT_Reviewer.exe` produced
- [ ] Smoke test: exe launches, first-run dialog on a clean profile, report
      generates, runs offline
- [ ] `pyproject.toml` and `installer.iss` versions match
- [ ] (If shipping the installer) Inno compile → `VPAT_Reviewer_Setup.exe`,
      installs and creates both Desktop subfolders
