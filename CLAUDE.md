# CLAUDE.md — VPAT Reviewer

**Read this first.** It's the map and the rulebook for this codebase. It's
written for the next person (or AI) picking up the project, who may be
vibe-coding with limited software background. Follow it and you can add features
without breaking the parts that took real effort to get right.

If you change how the project is structured, **update this file in the same
change.** A stale map is worse than none.

---

## 1. What this app is

A **fully offline** desktop tool. You give it a vendor's **VPAT**
(Voluntary Product Accessibility Template — a PDF, DOCX, or TXT that says how
accessible a product is), and it produces a **branded PDF compliance report**:
a WCAG conformance score, the accessibility barriers, and a plain-language
impact assessment. No internet, no API keys, no cloud — everything runs on the
user's machine, and the shippable form is a single `VPAT_Reviewer.exe`.

Users are accessibility reviewers at an educational network (SFBRN). The people
generating reports are not technical; the person maintaining the code (you) has
these docs.

---

## 2. Golden rules — do not break these

These are load-bearing. If a change would violate one, stop and reconsider.

1. **The behavior anchor must hold.** Run `python make_demo.py`. It must print:
   ```
   Score: 72 | supported: 13 | reviewable: 18 | NA excluded: 2
   Validation: OK
   ```
   This is the canary for the whole scoring pipeline. If it changes, you changed
   scoring behavior — make sure that was intentional and update the tests.

2. **All quality gates stay green** before you commit:
   ```
   ruff check .        # lint + import order
   ruff format .       # formatting
   mypy                # strict type-checking of src/vpat_reviewer
   python -m pytest -q # the whole test suite
   ```

3. **Scoring policy is "Option A": `Not Applicable` is excluded from the
   denominator _and_ from the barrier count.** This is a deliberate domain
   decision, encoded in `GradingPolicy.excluded_statuses`. Don't "fix" it.

4. **The domain layer stays pure.** `src/vpat_reviewer/domain/` must not import
   pdfplumber, python-docx, reportlab, tkinter, or the filesystem. It's just
   data and rules, which is why it's easy to test. (See §4 for the dependency
   direction.)

5. **Don't rewrite the parser or the ReportLab renderer without a fixture that
   proves you didn't regress.** See §8. These modules are full of hard-won,
   real-world fixes.

---

## 3. Architecture in one picture

Ports & adapters (a.k.a. hexagonal). A pure core, with all the messy
outside-world stuff (file formats, PDF drawing, the GUI) as swappable adapters
around it.

```
                 ┌─────────────────────────────────────────────┐
   INPUT         │                  CORE (pure)                 │        OUTPUT
                 │                                              │
  PDF ─┐         │   parsing/  →  domain/  →  reporting inputs  │        ┌─ PDF report
  DOCX ─┼─ extraction/ ─────────────►  models / scoring /  ─────┼─ reporting/ ─► (ReportLab)
  TXT ─┘  (Extractor port)         impact / policy             │  (ReportRenderer port)
                 │                       ▲                      │
                 │                       │ reads               │
                 │                  reference/ (wcag.json)      │
                 └───────────────────────┬──────────────────────┘
                                         │ orchestrated by
                              service.py  →  cli.py / ui.gui (adapters)
                                         │ configured by
                                   config/ (settings.json: identity + grading policy)
```

**Dependency rule:** arrows point _inward_. `domain/` depends on nothing.
`parsing/`, `reference/`, `reporting/` depend on `domain/`. `service.py` wires
them. `cli.py` and `ui/gui/` are the outermost adapters and depend on
`service.py`. Never make an inner layer import an outer one.

---

## 4. Where everything lives

```
<project root>/
├─ CLAUDE.md               ← you are here
├─ BUILD_INSTRUCTIONS.md   ← how to produce the .exe / installer
├─ README.md               ← end-user / project overview
├─ docs/
│  ├─ architecture.md      ← deeper design notes + the phase history
│  └─ extending.md         ← step-by-step recipes (also summarized in §6 here)
├─ pyproject.toml          ← deps, tooling config, console-script entry points
├─ vpat_reviewer.spec      ← PyInstaller recipe (bundles wcag.json + deps)
├─ build_exe.bat           ← one-click build → dist/VPAT_Reviewer.exe
├─ installer.iss           ← optional Inno Setup click-through installer
├─ make_demo.py            ← the behavior anchor (Score: 72 …)
│
├─ src/vpat_reviewer/          ← THE PACKAGE. New code goes here.
│  ├─ __init__.py              ← public API + __version__
│  ├─ service.py               ← analyze() / render_result() / review() (orchestration)
│  ├─ cli.py                   ← `vpat-review` command-line interface
│  ├─ diagnostics.py           ← headless self-test (`--selftest`)
│  │
│  ├─ domain/                  ← PURE core. No I/O, no third-party libs.
│  │  ├─ models.py             ← VPATCriterion, VPATDocument (the data)
│  │  ├─ normalization.py      ← raw vendor status text → 5 canonical statuses
│  │  ├─ policy.py             ← GradingPolicy: the EDITABLE grading rules ★
│  │  ├─ scoring.py            ← compliance_score(), get_barriers()
│  │  └─ impact.py             ← calculate_impact() (audience/access/legal/scale)
│  │
│  ├─ extraction/              ← File bytes → text + tables. (Extractor port)
│  │  ├─ base.py               ← RawDocument + the Extractor Protocol
│  │  ├─ pdf.py / docx.py / txt.py   ← one adapter per format
│  │  └─ registry.py           ← picks the extractor by file extension
│  │
│  ├─ parsing/                 ← text/tables → VPATDocument (the hard part)
│  │  ├─ document.py           ← parse_vpat() / parse_document() entry points
│  │  ├─ criteria.py           ← the criterion-row regex + table/text parsers
│  │  ├─ metadata.py, dates.py, standards.py, section508.py, text_cleanup.py
│  │
│  ├─ reference/               ← WCAG knowledge (data, not code)
│  │  ├─ loader.py             ← all_criteria(), lookup(), has_all_required()
│  │  └─ data/wcag.json        ← 54 criteria: titles, descriptions, workarounds ★
│  │
│  ├─ reporting/               ← VPATDocument + score → PDF. (ReportRenderer port)
│  │  ├─ base.py               ← ReportInputs + the ReportRenderer Protocol
│  │  ├─ __init__.py           ← ReportLabRenderer (the adapter class)
│  │  └─ reportlab_renderer.py ← 83KB legacy layout engine (isolated; see §7)
│  │
│  ├─ config/                  ← everything the user can edit
│  │  ├─ settings.py           ← settings.json store (identity + grading policy)
│  │  └─ policy_form.py        ← UI-agnostic policy editing + validation ★
│  │
│  └─ ui/gui/                  ← Tkinter desktop app (outermost adapter)
│     ├─ app.py                ← the window, the pipeline, main()
│     └─ policy_dialog.py      ← the grading-policy editor dialog
│
├─ tests/                      ← mirrors the package (see §5)
│  ├─ unit/  parsing/  reporting/  fixtures/
│
├─ run_app.py                  ← GUI launcher + PyInstaller entry point (see §7)
├─ make_demo.py                ← the behavior anchor / sample generator
└─ test_v10_regression.py     ← original end-to-end regression suite
```

★ = the "make it editable" surfaces the user specifically cares about.

---

## 5. How to run everything

From the project root, with a dev install (`pip install -e ".[dev]"`):

| Task | Command |
|---|---|
| Run the tests | `python -m pytest -q` |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Type-check | `mypy` |
| Behavior anchor | `python make_demo.py` → `Score: 72 … Validation: OK` |
| CLI: score a VPAT | `python -m vpat_reviewer.cli analyze path/to/vpat.pdf` |
| CLI: full report | `python -m vpat_reviewer.cli review path/to/vpat.pdf -o out.pdf` |
| CLI: see grading policy | `python -m vpat_reviewer.cli policy show` |
| CLI: edit a policy knob | `python -m vpat_reviewer.cli policy set compliance_threshold 85` |
| CLI: edit identity | `python -m vpat_reviewer.cli settings set org_name "Acme"` |
| Launch the GUI | `python run_app.py` |
| Build the .exe | `build_exe.bat` (see BUILD_INSTRUCTIONS.md) |
| Verify a built .exe | `dist\VPAT_Reviewer.exe --selftest` → writes `vpat_selftest.json` |

Installed console scripts (after `pip install -e .`): `vpat-review` (CLI) and
`vpat-review-gui` (GUI).

---

## 6. How to extend (recipes)

Full versions with code are in `docs/extending.md`. The shape:

### Add a new input format (e.g. `.odt`)
1. Write `extraction/odt.py` with a class exposing
   `extensions: tuple[str, ...] = (".odt",)` and an `extract(path) -> RawDocument`
   method. Follow `txt.py` for the simplest template.
2. Register it in `extraction/registry.py`.
3. Add a fixture + a test under `tests/parsing/`.
   *You don't touch parsing or domain code — that's the point of the port.*

### Add a new output format (e.g. HTML or DOCX report)
1. Write a renderer class implementing the `ReportRenderer` Protocol from
   `reporting/base.py` (`output_suffix` + `render(inputs, output_path)`).
2. Pass an instance to `service.render_result(..., renderer=YourRenderer())`.
   *The existing PDF renderer is just one adapter; add others beside it.*

### Change or add a grading knob (the editable grading system)
- Grading lives entirely in `domain/policy.py` as the `GradingPolicy`
  dataclass. It is **data**: every field has a default, and the whole thing
  round-trips to/from JSON (`to_dict` / `from_dict`) and is stored under the
  `"grading"` key in `settings.json`.
- To expose an existing knob in the friendly editors, add it to
  `EDITABLE_FIELDS` (or the band handling) in `config/policy_form.py` — that
  module is the single source of truth the CLI (`policy set`) and the GUI dialog
  both use, and it's where validation lives.
- Add/adjust a test in `tests/unit/test_policy.py` or `test_policy_form.py`.
- **Always** keep `GradingPolicy.default()` producing the anchor score (72).

Key `GradingPolicy` fields: `graded_level` ("A"/"AA"), `supported_statuses`,
`excluded_statuses`, `compliance_threshold`, `score_bands`, `core_block_status`,
`scale_weights`, `access_flags`, `legal_flags`, `scale_flags`, `score_flags`.

### Add or edit WCAG reference text
- Edit `reference/data/wcag.json` (title / level / description / plain-language
  explanation / workarounds). **No code change needed** — `reference/loader.py`
  just serves it, and the report quotes it.
- If you add a criterion the app must always cover, add its id to `REQUIRED_IDS`
  in `loader.py`; `has_all_required()` and the self-test will enforce it.
- After editing, run `python run_app.py --selftest` (or the tests) to confirm
  the dataset still loads and is complete.

### Add a CLI command
- Add a subparser in `cli.py::build_parser` and a `_cmd_*` handler. Keep it a
  thin wrapper over `service`/`config` — no business logic in the CLI.

---

## 7. The root scripts and the "legacy" modules

This project was migrated incrementally (strangler-fig) from a flat pile of
scripts into the package. The backward-compat shims that migration used
(`vpat_parser.py`, `report_generator.py`, `wcag_reference.py`,
`settings_manager.py`) have since been **removed** — everything imports the
package directly now. Three genuine scripts remain at the root:

- **`run_app.py`**: launches the GUI (`python run_app.py`) and is the
  **PyInstaller entry point** the `.exe` is frozen from (see
  `vpat_reviewer.spec`). Keep it thin — it just calls into the package (and
  routes `--selftest`). **Do not delete it**; the build depends on it.
- **`make_demo.py`**: builds a sample report and prints the behavior anchor
  (`Score: 72 | … | Validation: OK`). It imports from the package directly.
- **`test_v10_regression.py`**: the original end-to-end regression suite (also
  runnable without pytest). Imports from the package directly.

Two legacy-style *modules inside the package* are intentionally isolated:

- **`reporting/reportlab_renderer.py`**: the original 83KB PDF layout engine.
  It's legacy-style (long, untyped) but it produces the approved report design,
  so it's **isolated behind the `ReportRenderer` port** and **excluded from ruff
  and mypy** (see `pyproject.toml`). Treat it as a black box: change it only
  with a before/after PDF comparison, and prefer adding a new renderer over
  rewriting this one. The `ui/` GUI is excluded from strict gates for the same
  reason (Tkinter, manually verified).

Everything else in `src/vpat_reviewer/` is new, typed, and linted — hold new
code to that standard.

---

## 8. Testing philosophy — why you can trust changes

- **Golden fixtures.** `tests/fixtures/txt/*.txt` are sample VPATs paired with
  `*.expected.json` (the parse we expect). `tests/parsing/test_fixtures.py`
  parses each and asserts it matches. This is the safety net that lets you
  refactor the parser: if a fixture's output changes, you'll know instantly.
  **When you fix a parser bug, add a fixture that reproduces it first.**
- **Unit tests** for the pure domain (`tests/unit/`) — scoring, impact, policy,
  normalization. Fast and exhaustive because the domain has no I/O.
- **The behavior anchor** (`make_demo.py`, mirrored by
  `test_v10_regression.py`) guards the end-to-end score.
- Tests pass `VPAT_SETTINGS_PATH` / explicit policies for determinism — never
  depend on a real user's `settings.json`.

Run the whole thing with `python -m pytest -q`. Adding a feature? Add its test
in the mirrored folder.

---

## 9. Conventions

- **Python 3.10+**, `from __future__ import annotations` at the top of modules.
- **src-layout**: the importable package is `src/vpat_reviewer`. Tests find it
  via `pythonpath = ["src", "."]` in `pyproject.toml`.
- **Line length 100.** Ruff enforces `E, F, I, UP, B, SIM, C4`.
- **mypy `--strict`** for the whole package (except the two isolated legacy
  areas). Type everything you add. No bare `# type: ignore` without a code.
- **Naming/comments**: match the surrounding file. Comments explain _why_, not
  _what_. Docstrings on modules and public functions.
- **Errors that must never crash the app** (corrupt settings, bad user file)
  are caught narrowly with a `# noqa: BLE001` and a comment saying why.
- **Version** is in `pyproject.toml` and `__init__.py.__version__` (keep them in
  sync) and mirrored in `installer.iss`.

---

## 10. Common gotchas

- **Windows/Git Bash line endings.** `.gitattributes` normalizes to LF; you'll
  see "LF will be replaced by CRLF" warnings — harmless.
- **`wcag.json` in the built exe.** It's loaded via `importlib.resources`, so
  PyInstaller needs it declared in `vpat_reviewer.spec` (`datas`). If a build
  can't find WCAG data at runtime, that's the first place to look; `--selftest`
  will catch it.
- **`settings.json` location.** Dev: project root. Frozen exe: next to the exe
  (`config/settings.py::default_settings_path`, keyed off `sys.frozen`). Tests
  override with `VPAT_SETTINGS_PATH`.
- **Don't commit build junk.** `.gitignore` covers `build/`, `dist/`,
  `__pycache__/`, tool caches, and generated `*.pdf`.

---

## 11. Where to read more

- `docs/architecture.md` — the design rationale and the full phase-by-phase
  migration history (how this got from a flat script pile to here).
- `docs/extending.md` — the recipes in §6 with complete code examples.
- `BUILD_INSTRUCTIONS.md` — building and releasing the exe/installer.
