# Extending the app — step-by-step recipes

Concrete, copy-pasteable recipes for the common changes. Each one names the
files to touch, gives working code, and tells you what test to add. Read
`CLAUDE.md` §2 (golden rules) before you start; run the gates (`ruff`, `mypy`,
`pytest`, `make_demo.py`) after.

The guiding principle: **most features are a new adapter or a data edit, not a
change to the core.** If a change forces you to edit `domain/`, pause and check
you're not putting technology-specific logic where the pure rules live.

---

## Recipe 1 — Support a new input format (e.g. `.odt`)

Ports make this a self-contained add. You will **not** touch parsing, scoring,
or the domain.

**1. Create the adapter** `src/vpat_reviewer/extraction/odt.py`:

```python
"""OpenDocument Text (.odt) extractor."""

from __future__ import annotations

from vpat_reviewer.extraction.base import RawDocument, Table


class OdtExtractor:
    extensions: tuple[str, ...] = (".odt",)

    def extract(self, path: str) -> RawDocument:
        text = _read_text(path)          # your library calls here
        tables: list[Table] = _read_tables(path)
        return RawDocument(text=text, tables=tables)
```

The class just needs to match the `Extractor` Protocol in `extraction/base.py`:
an `extensions` tuple and an `extract(path) -> RawDocument`. `RawDocument` holds
`text: str` and `tables: list[Table]` (a `Table` is `list[list[str | None]]`).

**2. Register it** in `src/vpat_reviewer/extraction/registry.py` — add your
extractor to the lookup that maps extensions to extractors (follow how `.pdf` /
`.docx` / `.txt` are wired). Add any alias extensions there too.

**3. Test it.** Drop a small sample under `tests/fixtures/` and add a test in
`tests/parsing/test_extraction.py` asserting your extractor returns the expected
text/tables. If the format is a common VPAT shape, also add a golden fixture
(see Recipe 5) so the *whole* parse is covered.

That's it — `service.analyze()` will now accept `.odt` files because it resolves
the extractor through the registry.

---

## Recipe 2 — Add a new report format (e.g. HTML or DOCX output)

The PDF renderer is one adapter behind the `ReportRenderer` port. Add another
beside it.

**1. Implement the port** `src/vpat_reviewer/reporting/html_renderer.py`:

```python
"""HTML report renderer."""

from __future__ import annotations

from vpat_reviewer.reporting.base import ReportInputs


class HtmlRenderer:
    output_suffix = ".html"

    def render(self, inputs: ReportInputs, output_path: str) -> None:
        html = _build_html(inputs)       # inputs.document, .score, .impact, .settings…
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
```

`ReportInputs` (see `reporting/base.py`) carries everything a report needs:
`document`, `score`, `impact`, `answers`, `logo_path`, `settings`.

**2. Use it** — pass an instance to the service:

```python
from vpat_reviewer.reporting.html_renderer import HtmlRenderer
service.render_result(result, "out.html", renderer=HtmlRenderer())
```

**3. Test it** in `tests/reporting/` — render to a temp path and assert the file
exists and contains the score/product name. (No need to re-test the analysis;
that's covered elsewhere.)

You don't have to modify the existing `ReportLabRenderer` — leave the approved
PDF exactly as it is.

---

## Recipe 3 — Change or add a grading knob (the editable grading system)

Grading is **data** in `domain/policy.py::GradingPolicy`. There are three levels
of change:

### (a) Change a value a user should control at runtime
Nothing to code — it's already editable:
```
python -m vpat_reviewer.cli policy set compliance_threshold 85
python -m vpat_reviewer.cli policy show
```
or via the GUI's "Grading Policy…" dialog. Stored in `settings.json`.

### (b) Expose an *existing* policy field in the friendly editors
Add it to `EDITABLE_FIELDS` in `config/policy_form.py`:

```python
EDITABLE_FIELDS: list[dict[str, Any]] = [
    # …existing…
    {"key": "core_block_status", "label": "Status that blocks core function",
     "type": "choice", "choices": list(CANONICAL_STATUSES)},
]
```

`config/policy_form.py` is the **single validated editing layer** the CLI and
GUI both use — put validation there, not in either UI. Add a case to `set_field`
if the new field needs special parsing.

### (c) Add a brand-new rule
1. Add a field (with a default) to the `GradingPolicy` dataclass in
   `domain/policy.py`.
2. Handle it in `to_dict` / `from_dict` so it persists.
3. Use it wherever the rule applies (`scoring.py` / `impact.py`).
4. Add it to `validate()` if there are invalid values to reject.
5. Optionally expose it in `policy_form.py` (see (b)).

**In all cases:** add/adjust a test in `tests/unit/test_policy.py` or
`test_policy_form.py`, and confirm `python make_demo.py` still prints
`Score: 72 … Validation: OK` (the default policy must keep producing the anchor).

Current fields for reference: `graded_level`, `supported_statuses`,
`excluded_statuses`, `compliance_threshold`, `score_bands`, `core_block_status`,
`scale_weights`, `access_flags`, `legal_flags`, `scale_flags`, `score_flags`,
`level_high_min_high_flags`, `level_medium_min_medium_flags`.

---

## Recipe 4 — Edit or add WCAG reference text

Pure data, no code change.

1. Open `src/vpat_reviewer/reference/data/wcag.json`. Each entry is keyed by
   criterion id:
   ```json
   "1.4.3": {
     "title": "Contrast (Minimum)",
     "level": "AA",
     "principle": "Perceivable",
     "description": "Official WCAG wording…",
     "plain_language": "What it means in everyday terms…",
     "workarounds": ["Interim workaround one", "…"]
   }
   ```
2. Edit or add entries. The report quotes `description` / `plain_language` and
   lists `workarounds`.
3. If the app must always cover a new criterion, add its id to `REQUIRED_IDS` in
   `reference/loader.py` — then `has_all_required()` (and the `--selftest`)
   enforce its presence.
4. Verify: `python run_app.py --selftest` (or `pytest tests/unit/test_reference.py`).

---

## Recipe 5 — Add a golden parser fixture (do this when you fix a parser bug)

The golden corpus is what makes parser changes safe. When you hit a VPAT that
parses wrong, capture it as a fixture *first*, then fix the parser.

1. Add the sample as `tests/fixtures/txt/<name>.txt` (trim it to the smallest
   text that reproduces the issue).
2. Create `tests/fixtures/txt/<name>.expected.json` describing the parse you
   expect (match the shape of the existing `acme_basic.expected.json`).
3. `tests/parsing/test_fixtures.py` picks it up automatically and asserts the
   parse matches. Run `pytest tests/parsing/test_fixtures.py`.
4. Now change the parser (`parsing/criteria.py` etc.) until the new fixture
   passes **and all existing fixtures still pass**. That green bar is your proof
   you fixed the bug without regressing the others.

---

## Recipe 6 — Add a CLI command

Keep the CLI a thin wrapper; business logic goes in `service`/`config`.

In `cli.py::build_parser`, add a subparser and set its handler:

```python
p_export = sub.add_parser("export", help="Export the analysis as JSON.")
p_export.add_argument("input")
p_export.set_defaults(func=_cmd_export)
```

Then the handler:

```python
def _cmd_export(args: argparse.Namespace) -> int:
    result = service.analyze(args.input)
    print(json.dumps(_result_dict(result), indent=2))
    return 0 if result.has_criteria else 1
```

Add a test in `tests/test_cli.py` calling `cli.main([...])` and asserting the
exit code / output.

---

## After any change — the checklist

```
ruff check .        # lint
ruff format .       # format
mypy                # types (strict, package only)
python -m pytest -q # tests
python make_demo.py # anchor: Score: 72 | … | Validation: OK
```

If you touched packaging or data loading, also rebuild and self-test:

```
build_exe.bat
dist\VPAT_Reviewer.exe --selftest      # writes vpat_selftest.json, exit 0 = good
```

Green across the board → commit. Something red → fix before moving on; a broken
gate is the cheapest bug you'll ever catch.
