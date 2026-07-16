# Test fixtures

This folder holds sample VPAT inputs and their **golden** (expected) parse output.
They are the parser's regression safety net: if a change alters how any
realistic VPAT parses, `tests/parsing/test_fixtures.py` fails.

## Layout

```
fixtures/
└── txt/
    ├── <name>.txt            # a sample VPAT (plain-text form)
    └── <name>.expected.json  # frozen, normalized parse result (the "golden")
```

`.txt` fixtures exercise metadata extraction, WCAG text-fallback parsing,
standards detection, and the Section 508 functional-performance fallback.
Table-based DOCX behavior (merged cells, cover tables) is covered separately by
`tests/parsing/test_docx_roundtrip.py`, which builds a `.docx` on the fly.

## Adding a fixture

1. Drop a new `tests/fixtures/txt/<name>.txt`.
2. Generate its golden and review it:

   ```bash
   VPAT_REGEN_FIXTURES=1 python -m pytest tests/parsing/test_fixtures.py
   ```

   On Windows PowerShell:

   ```powershell
   $env:VPAT_REGEN_FIXTURES=1; python -m pytest tests/parsing/test_fixtures.py; Remove-Item Env:VPAT_REGEN_FIXTURES
   ```

3. Open `<name>.expected.json` and confirm the values are what you expect
   (product name, criteria, statuses, score, barriers). **Do not** commit a
   golden you have not eyeballed — a wrong golden freezes a bug.
4. Commit both files.

## What's in the golden

A normalized, **deterministic** subset of the parse result. Date-derived fields
(`is_outdated`, `outdated_note`, the parsed date object) are deliberately
excluded because they depend on today's date. The raw report-date *string*
(`vendor_report_date_raw`) is included.

Note: Section 508 functional-performance rows (302.1–302.9, `section: "508_fpc"`,
`level: ""`) appear only when the document actually states them — from a table
row, or from prose naming the criterion and its conformance value. They do not
affect the WCAG AA score, which counts only `level: "AA"`.

Until July 2026 the parser emitted all nine rows unconditionally, defaulting the
status to `Not Evaluated`, and the goldens here froze that as expected output.
Both fixtures contain no `302` text at all, so those eighteen rows were pure
invention — and every document got them, including files that were not VPATs.
If you see fabricated rows come back, that fallback has regressed.
