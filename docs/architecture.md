# Architecture & design rationale

This is the "why it's built this way" companion to `CLAUDE.md` (which is the
"where things are / what not to break" map). Read `CLAUDE.md` first.

## The shape: ports & adapters

The app is organized as a **pure core** surrounded by **adapters**:

- **Core (pure, no I/O):** `domain/` — the data (`VPATCriterion`,
  `VPATDocument`), the rules (`scoring`, `impact`, `normalization`), and the
  editable configuration object (`policy`). It imports nothing heavier than the
  standard library. That purity is *why the core is trivially testable* — no
  files, no PDF library, no GUI to stand up.
- **Ports (interfaces):** small Protocols that say what the core needs from the
  outside world without naming a specific technology:
  - `extraction/base.py::Extractor` — "give me text + tables from a file."
  - `reporting/base.py::ReportRenderer` — "turn an analysis into a report file."
- **Adapters (implementations):** the concrete, messy, technology-specific code
  that satisfies a port — `extraction/pdf.py` (pdfplumber), `extraction/docx.py`
  (python-docx), `reporting/reportlab_renderer.py` (ReportLab), `ui/gui/`
  (Tkinter). Any of these can be swapped or added-to without touching the core.

```
   adapters  →  ports  →  core  ←  ports  ←  adapters
  (pdf/docx)   Extractor  domain  ReportRenderer  (reportlab/…)
```

### Why this shape for this project

- **Testability.** The domain has no dependencies, so scoring/impact/policy are
  covered by fast, exhaustive unit tests. The risky, format-specific code is
  quarantined behind ports and covered by golden fixtures.
- **Change safety.** Adding a `.odt` reader or an HTML report is a new adapter,
  not a change to the rules. The blast radius of a feature is small.
- **A legacy engine we must keep.** The 83KB ReportLab layout code produces an
  approved, pixel-specific report. Rewriting it is high-risk and low-value. As
  an adapter behind `ReportRenderer`, it stays exactly as it was, isolated from
  the linter/type-checker, while everything around it is clean and typed.

## The dependency rule

Dependencies point **inward** only:

```
ui/gui, cli  →  service  →  parsing, reference, reporting  →  domain
```

`domain/` never imports anything above it. `service.py` is the only place that
knows about the whole pipeline; it wires parsing → scoring → impact → rendering
and pulls defaults from `config/`. The CLI and GUI are thin: they collect input,
call `service`, and present the result. If you find yourself importing `tkinter`
in `domain/`, or `scoring` importing `pdfplumber`, the layering is inverted —
stop.

## Data, not code: the two editable surfaces

Two things the user explicitly needs to change without a developer:

1. **The grading system** — `domain/policy.py::GradingPolicy`. A frozen
   dataclass where every rule is a field with a default. It serializes to JSON
   and back (`to_dict`/`from_dict`), so a user's edits live in `settings.json`
   under `"grading"`. `config/policy_form.py` is the one validated editing layer
   the CLI and GUI share. Changing a grade weight is editing data, not patching
   `if` statements.
2. **The WCAG reference text** — `reference/data/wcag.json`. Titles,
   descriptions, plain-language explanations, and workarounds are data the
   report quotes. `reference/loader.py` only loads and serves it.

The design goal behind both: *the things that change often are data; the code
that processes them is stable.*

## The scoring decision ("Option A")

Compliance score = supported ÷ reviewable, where **`Not Applicable` criteria are
excluded from the denominator and from the barrier count**, but still *appear*
in the report as transparently documented gaps. This is encoded as
`GradingPolicy.excluded_statuses = ("Not Applicable",)`, not hard-coded, so it's
auditable and adjustable — but it is a deliberate policy, and the demo anchor
(score 72) depends on it. Don't change it casually.

## Configuration & the frozen app

`config/settings.py` is a single non-destructive store for both organization
identity (org name, reviewer, threshold, logo) and the grading policy. Writing
one never clobbers the other. `default_settings_path()` returns the project root
in development and the executable's own folder when frozen (`sys.frozen`), so a
shared `.exe` keeps its settings beside it. Tests override the location with the
`VPAT_SETTINGS_PATH` environment variable.

## Packaging

`vpat_reviewer.spec` freezes `run_app.py` into a single
`dist/VPAT_Reviewer.exe`. Two non-obvious needs it handles: bundling
`wcag.json` at its package path (it's loaded via `importlib.resources`, so
PyInstaller won't grab it automatically) and collecting the dynamically-imported
submodules of reportlab/pdfplumber/pypdf/python-docx. `diagnostics.py` provides
`--selftest`, a headless check that the frozen app can load its data and imports
— run it on every fresh build. Details in `BUILD_INSTRUCTIONS.md`.

---

## Migration history (how we got here)

The app started as a flat pile of scripts (`run_app.py`, `report_generator.py`,
`vpat_parser.py`, `wcag_reference.py`, …) whose file *contents* had been
shuffled and misnamed. It was reconstructed, then re-architected **incrementally
(strangler-fig)** — at every phase the app stayed working and the behavior
anchor (score 72) held. Backward-compat shims preserved the old import paths
during the migration and were removed once nothing depended on them; today
everything imports the package directly.

| Phase | What landed |
|---|---|
| 0 | src-layout package, tooling (ruff/mypy/pytest/pre-commit), CI |
| 1 | Pure domain extracted (`models`, `normalization`, `scoring`, `impact`) + the editable `GradingPolicy` |
| 2 | Split file **extraction** (I/O) from **parsing** (text → model); `Extractor` port + registry |
| 3 | Golden-fixture test corpus as the parser safety net (kept the battle-tested regexes rather than risk silent regressions) |
| 4 | WCAG moved from code to **data** (`reference/data/wcag.json`) behind a loader |
| 5 | Reporting put behind the `ReportRenderer` port; legacy ReportLab engine isolated |
| 6 | `service.py` orchestration + the `vpat-review` CLI |
| 7 | GUI became a thin adapter; full **editable settings** (identity + grading) via the shared `policy_form` layer, CLI `policy`/`settings` commands, and a GUI dialog |
| 8 | Single-file **exe** packaging (`vpat_reviewer.spec` + `build_exe.bat`), `--selftest`, updated installer/build docs |
| 9 | This documentation set (`CLAUDE.md` + `docs/`) for the next maintainer |

### Why the parser wasn't "cleaned up"

Phase 3 deliberately did **not** rewrite the criterion-matching regexes. They
encode real fixes for real vendor VPATs (merged DOCX cells, cover-page tables,
date formats, status-normalization ordering, Section 508 FPC handling, vendor
remark scan windows). Without a large corpus of real vendor files, rewriting
them risks silent, hard-to-notice regressions on documents we can't see. Instead
we built the golden-fixture net so that *when* you do refactor the parser, any
behavior change is caught immediately. Cleaning it up is safe **once fixtures
cover the cases you're changing** — not before.

## Parser hardening (July 2026) — and what the corpus taught us

The caveat above ("without a large corpus of real vendor files") stopped being
true: `docs/completed_forms/` now holds twelve real documents, and
`tools/corpus_report.py` measures the parser against them. Running it the first
time was sobering. **Three of the six real VPATs had almost every status wrong**
— Atrium reported 55 of 56 criteria as "Not Evaluated", H5P all 87, Canvas 40 of
50 — and the unit tests were entirely green throughout.

### The lesson: the failure mode is silence, not noise

None of those bugs threw. Each one read an empty cell and normalized `""` to
`Not Evaluated`, which is a *plausible* answer, so nothing downstream could tell.
The report printed a confident percentage over fabricated data.

That is why the design now leans on two ideas:

1. **Report only what the document states.** `parse_508_fpc` used to synthesize
   all nine `302.x` functional performance rows on every document — including
   files that were not VPATs at all — and the goldens had frozen those eighteen
   invented rows as expected output. A row with no evidence behind it is not a
   finding.
2. **Say what kind of document this is.** `parsing/doctype.py` classifies before
   anything is scored, and the CLI refuses a non-VPAT with a distinct exit code.
   Scoring a remediation plan is worse than failing: it produces a number that
   looks authoritative and means nothing.

### The structural fix: look, don't index

The single root cause behind Atrium, H5P and Canvas was `parse_from_tables`
deciding the status column from the table's *width* (`9col` or `3col`, sniffed
once from the first matching row). Real templates are 3, 5, 8 and 9 columns wide.
`find_row_status` now scans each row for the cell that **is** a conformance value
— strict, full-cell, after stripping any target prefix — which handles all
observed widths and is inherently robust to the next one.

The corresponding lesson for extraction: a PDF cell is not a string, it is a
region of a page. `extraction/pdf.py::_overlay_fonts` drops watermark characters
that fall inside cells by **geometry** (overlay text has no horizontally adjacent
same-font neighbours) rather than by font name, and
`criteria.py::_absorb_continuation` reattaches remarks that a vendor split across
one table row per line. Both are cases where the naive string view of a cell is
simply the wrong model.

### Where this leaves the "don't rewrite the parser" rule

It still holds, but the reason has sharpened. The regexes are not sacred; the
*behaviour on real documents* is. The corpus scoreboard, not the unit tests, is
what makes a parser change safe — `--check` fails when coverage drops or
unresolved rows rise. Refactor freely with it green; do not touch the parser
without it. See CLAUDE.md §7a.
