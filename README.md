# SFBRN VPAT Reviewer — v11

A Windows desktop app that reads a vendor's VPAT document (PDF, Word, or
text) and produces a branded, professionally styled **VPAT Accessibility
Compliance — Summary Report** as a PDF. Everything runs on your own
computer: no internet, no accounts, no API keys, nothing leaves the machine.

This README is the friendly overview. If you're going to **change the code**
(or you're an AI doing so), read **`CLAUDE.md`** next — it's the map and the
rulebook. Deeper design notes are in **`docs/`**; building the `.exe` is in
**`BUILD_INSTRUCTIONS.md`**.

---

## The big picture: how the app is put together

The same "assembly line" as always — a file goes in one end and a finished
report comes out the other — but the code now lives in a proper, tidy Python
package under `src/vpat_reviewer/`, split so each part has one job:

1. **The reader** (`extraction/` + `parsing/`) opens the vendor's document and
   pulls out the product name, dates, WCAG rows, statuses, and remarks. This is
   the most battle-tested part of the project, so **we never edit it casually.**
2. **The rules** (`domain/`) calculate the compliance score, find the barriers,
   and rate the impact. This part is "pure" — it does no file or PDF work — which
   is why it's easy to test and hard to break.
3. **The dictionary** (`reference/`) stores, for every WCAG criterion (like
   "1.4.3 Contrast (Minimum)"), the official description and a plain-language
   explanation. It's just a data file (`reference/data/wcag.json`) you can edit.
4. **The writer** (`reporting/`) lays out the actual PDF: cover page, executive
   summary, barrier cards, tables, page-numbered footer, colors, and fonts.

Two things tie it together and let people use it:

- **The window** (`ui/gui/`) is the graphical interface (buttons, drag-and-drop,
  Settings). It just collects your input and hands the job to the parts above.
  There's also a **command line** (`cli.py`) for the same thing without a window.
- **The settings** (`config/`) remember who is using the app *and* let you edit
  the **grading rules** — both saved in a small `settings.json`. Nothing is
  hard-wired to one organization.

Keeping the "screen" separate from the "brains" is a core software habit: you
can change how the app *looks* without risking the logic that makes it *correct*.

---

## Why this is a Python app and not the Electron/React stack in the brief

The project brief suggested Electron + React + a Python backend, *"unless there
is a strong technical reason to choose an equivalent approach."* There is one:

- **One language, not four.** This app is Python end to end. The Electron route
  means juggling JavaScript, React, HTML/CSS, *and* Python — four things to learn
  and four things that can break.
- **It protects working code.** The reader already contains many hard-won fixes
  for messy real-world VPATs (merged Word tables, weird date formats, vendor
  typos in status words). Rebuilding from scratch would reintroduce solved bugs.
- **It meets every requirement:** fully offline, no API keys, local-only storage,
  the Desktop folder structure, single-click install, SFBRN branding, all report
  sections, and PDF validation.

The *goals* of the brief are met; only the toolkit differs, for good reasons.

---

## The one rule to remember

**Don't change how scoring or parsing behave without re-running the tests.**
The whole point of the test suite is to catch it the instant you do. After any
change, from inside this folder:

```
python -m pytest -q          # everything must pass
python make_demo.py          # must print: Score: 72 | … | Validation: OK
```

That "Score: 72 … Validation: OK" line is the app's canary — if it changes, you
changed the scoring, so make sure that was on purpose. `CLAUDE.md` lists all the
"do not break" rules and shows how to extend the app safely.

---

## What's in this project (high level)

| Thing | Plain-English job |
|---|---|
| `src/vpat_reviewer/` | The app itself, as an importable Python package (all the parts above). |
| `run_app.py` | Launches the window. Also the entry point the `.exe` is built from. |
| `make_demo.py` | Builds a sample report so you can see the output. |
| `tests/` | Automated checks that guard the math, the parsing, and the layout. |
| `CLAUDE.md` | **Read this before changing code.** The map + rulebook. |
| `docs/` | Design notes (`architecture.md`) and how-to recipes (`extending.md`). |
| `BUILD_INSTRUCTIONS.md` | Step-by-step guide to build the `.exe` and installer. |
| `build_exe.bat` / `vpat_reviewer.spec` | Turn the code into one `VPAT_Reviewer.exe`. |
| `installer.iss` | Wrap the `.exe` in an optional single-click installer. |
| `pyproject.toml` | The project's dependencies and settings. |
| `INSTALL_INSTRUCTIONS.txt` | Hand this to end users. |

---

## How to run it right now (before packaging)

On your Windows machine, from inside this folder:

```
pip install -e ".[dev]"
python run_app.py
```

The first time it opens, a short setup window asks for your organization and
name. After that, drag a VPAT onto the window and click **Generate Report**.

Prefer the command line? `python -m vpat_reviewer.cli review path\to\vpat.pdf`.
To see an example without a real VPAT, run `python make_demo.py`.

## How to turn it into a shareable app

See `BUILD_INSTRUCTIONS.md`. The short version: run `build_exe.bat` to get one
self-contained `dist\VPAT_Reviewer.exe` you can hand to the team. Optionally,
open `installer.iss` in the free Inno Setup program and click Compile to get a
single-click installer, `VPAT_Reviewer_Setup.exe`. Verify any build with
`dist\VPAT_Reviewer.exe --selftest`.

---

## What "compliance score" means here

The score counts how many WCAG **Level AA** criteria the vendor fully supports,
divided by the Level AA criteria that actually apply, as a percentage. Criteria
the vendor marks **Not Applicable** are left out of that math (a feature that
doesn't exist can't pass or fail), but they still appear in the report as
documented "known gaps" so nothing is hidden. This behavior is deliberate, it
lives in the editable grading policy (`domain/policy.py`), and it's locked in by
the tests.
