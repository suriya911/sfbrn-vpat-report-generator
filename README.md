# SFBRN VPAT Reviewer

**Turn a vendor's accessibility paperwork into a decision you can act on.**

You give this app a vendor's VPAT — the document where a company states how
accessible its product is — and it hands back a branded PDF report with a clear
verdict: **Good to Go**, **Minor Issue**, **Needs Manual Review**, **Need TAAP**,
or **Deny**.

It reads the document, scores it against the WCAG accessibility standard, works
out who is affected and how badly, and writes the result in plain language, with
the evidence attached.

*Version 11.0.0 · Windows and macOS · Python 3.10+*

---

## Contents

- [What problem this solves](#what-problem-this-solves)
- [Quick start](#quick-start)
- [The five verdicts](#the-five-verdicts)
- [What the compliance score means](#what-the-compliance-score-means)
- [Does anything leave my computer?](#does-anything-leave-my-computer)
- [Where your files go](#where-your-files-go)
- [The audit log](#the-audit-log)
- [How the app is put together](#how-the-app-is-put-together)
- [Settings](#settings)
- [For developers](#for-developers)
- [Building the app to share](#building-the-app-to-share)

---

## What problem this solves

Before a college buys software, someone has to answer a hard question: **can
everyone use it?** — including people who are blind, deaf, or cannot use a mouse.

Vendors answer with a **VPAT** (Voluntary Product Accessibility Template): a long
document listing ~50 accessibility rules, with the vendor's own claim against
each one — *Supports*, *Partially Supports*, *Does Not Support*, *Not
Applicable*. They are tedious to read, inconsistent between vendors, and easy to
skim past.

This app reads one in seconds and tells you:

- **A score** — what fraction of the applicable rules the vendor claims to meet.
- **The barriers** — exactly which rules fail, and what each one means for a real
  person trying to use the product.
- **A verdict** — the recommended procurement decision.
- **The reasoning** — so a human can disagree with it.

> **It is not an audit.** The app reads what the *vendor said about themselves*.
> It does not test the product. A vendor can be wrong or optimistic, and this
> app will faithfully report what they claimed. It exists to make a human
> reviewer faster, not to replace them.

---

## Quick start

**If someone handed you `VPAT_Reviewer.exe`:** double-click it. Skip to
[The five verdicts](#the-five-verdicts).

**Running from the source code:**

```bash
pip install -e ".[dev]"
python run_app.py
```

The first run asks for your organization and your name — that's what appears on
the reports. Then:

1. **Drag a VPAT onto the window** (PDF, Word `.docx`, or `.txt`).
2. **Answer four questions** about how the product will be used (below).
3. **Click Generate Report.**

The report opens in a folder on your Desktop, filed by verdict.

### The four questions, and why they matter

The document tells the app how accessible the product *is*. Only you can say how
much that **matters here** — the same VPAT deserves a different answer for one
person's laptop than for a campus-wide rollout.

| Question | Why it changes the answer |
|---|---|
| How many users? | A barrier affecting 5,000 people is not the same problem as one affecting 1. |
| Does it limit access for users with disabilities? | The difference between "harder" and "impossible". |
| Legal exposure? | ADA / Section 504 risk. |
| Deployment scope? | Individual, department, or campus-wide. |

These produce an **impact level** (Low / Medium / High), and impact **outranks
the score** — see below.

### No window? Use the command line

```bash
python -m vpat_reviewer.cli review path/to/vendor_vpat.pdf
python make_demo.py          # see a sample report without a real VPAT
```

---

## The five verdicts

| Verdict | Meaning |
|---|---|
| **Good to Go** | Meets the bar. Approve as-is. |
| **Minor Issue** | Deployable, with small gaps to track. Ask the vendor for a fix timeline. |
| **Needs Manual Review** | Inconclusive. A human must test it before deciding. |
| **Need TAAP** | Gaps require a **Temporary Alternative Access Plan** before approval — a documented way for affected users to get equivalent access while the vendor fixes things. |
| **Deny** | Do not deploy. Barriers block required functionality. |

**How the verdict is reached** (when the app is offline, or the AI is
unavailable — first match wins, top to bottom):

| # | If… | Then |
|---|---|---|
| 1 | The score couldn't be calculated | Needs Manual Review |
| 2 | Denies access **and** High impact | Deny |
| 3 | High impact **and** score below 50% | Deny |
| 4 | High impact | Need TAAP |
| 5 | Score ≥ 90% **and** zero barriers | Good to Go |
| 6 | Score ≥ 70% | Minor Issue |
| 7 | anything else | Needs Manual Review |

Three things worth understanding:

- **Impact outranks the score.** High impact never does better than Need TAAP —
  even at 100%. A perfect score on software that denies access to a required
  function is not a pass.
- **A missing score is not a zero.** An unreadable document goes to a human, not
  to Deny. The app never guesses.
- **"Good to Go" is strict.** One *Partially Supports* at Level AA caps you at
  Minor Issue.

---

## What the compliance score means

> **Level AA criteria the vendor fully supports ÷ Level AA criteria that apply**

Criteria the vendor marks **Not Applicable** are excluded from *both* halves — a
feature that doesn't exist can't pass or fail. They still appear in the report as
documented known gaps, so nothing is hidden.

This is a deliberate policy decision, it lives in an editable file
(`domain/policy.py`), and the tests lock it in place.

---

## Does anything leave my computer?

**Yes — by default, the verdict comes from an AI model on Amazon Web Services.**
Read this before reviewing anything confidential.

- The app sends AWS the **parsed contents of the VPAT**: product and vendor
  names, every criterion, the vendor's own remarks, and the score. It does not
  send the original file.
- It runs on **every report**, automatically. Nothing asks first.
- A copy of what was sent and what came back is saved **unencrypted** in
  `Desktop\VPAT Reviewer Files\AI Prompts\` and `\AI Responses\`.

**To keep the app fully offline**, set `"use_ai": false` in `settings.json`. You
get the same report, with the verdict decided by the built-in rules above, and
nothing leaves your machine.

That is also what happens automatically whenever AWS can't be reached — the
report is still produced, and the app tells you which decided: **Verdict by:
Amazon Bedrock** or **Deterministic rules**. Every row of the
[audit log](#the-audit-log) records which one it was.

Everything else — reading the document, scoring, drawing the PDF — has always run
on your own computer and still does.

---

## Where your files go

Everything lands in one folder on your Desktop:

```
Desktop/VPAT Reviewer Files/
├── VPATs/                        a copy of each document you reviewed
├── VPAT Summary Reports/
│   ├── Good To Go/               reports, filed by verdict
│   ├── Minor Issue/
│   ├── Needs Manual Review/
│   ├── Need TAAP/
│   └── Deny/
├── AI Prompts/                   exactly what was sent to AWS
├── AI Responses/                 exactly what came back
└── vpat_review_log.csv           one row per review (see below)
```

---

## The audit log

Every review appends one row to `vpat_review_log.csv` — open it in Excel. It
answers the questions that come up months later: *what did we decide, why, and
was it a model or a rule that decided it?*

Alongside the score, verdict, barriers, and your four impact answers, each row
carries:

| Column | Why it's there |
|---|---|
| `verdict_source` | **`ai` or `offline`.** "Good to Go" from the model and from the built-in rules are the same words and very different claims. Nothing else in the row tells them apart. |
| `source_sha256` | A fingerprint of the exact file. A filename doesn't identify a document; the bytes do. |
| `unresolved_criteria` | Rows the app couldn't read a status for. A high number next to a confident-looking score means don't trust the score. |
| `input_tokens` / `output_tokens` | What the AI call cost. Blank — never `0` — when the provider didn't report it. |
| `ai_error` | Why there's no AI verdict, when there isn't one. |
| `report_path` / `json_path` | Where the report and the full machine-readable record landed. |

Turn it off with `"audit_log_enabled": false`, or move it with
`"audit_log_path"`.

---

## How the app is put together

### The plain-English version

Think of it as an **assembly line**. A document goes in one end; a finished
report comes out the other. Each station has exactly one job.

```
   Vendor's VPAT
   (PDF / Word / text)
          │
          ▼
   ┌──────────────┐   Opens the file and pulls out the words and tables.
   │  1. READER   │   Knows about PDF quirks, merged Word cells, watermarks.
   └──────────────┘
          │
          ▼
   ┌──────────────┐   Finds the product name, the dates, and every WCAG row
   │  2. PARSER   │   with the vendor's claim. Never invents one.
   └──────────────┘
          │
          ▼
   ┌──────────────┐   Scores it. Finds the barriers. Rates the impact using
   │  3. RULES    │   your four answers. Pure arithmetic — no files, no network.
   └──────────────┘
          │
          ├────────────────────────┐
          ▼                        ▼
   ┌──────────────┐        ┌──────────────┐
   │  4. VERDICT  │        │ 5. DICTIONARY│  Plain-language explanation and
   │  AI, or the  │        │  Every WCAG  │  workarounds for each criterion,
   │  built-in    │        │  rule, in    │  so the report explains what a
   │  rules       │        │  human words │  failure means for a real person.
   └──────────────┘        └──────────────┘
          │                        │
          └───────────┬────────────┘
                      ▼
              ┌──────────────┐
              │  6. WRITER   │   Draws the PDF: cover, summary, barriers,
              │              │   tables, branding.
              └──────────────┘
                      │
                      ▼
         Report  +  JSON record  +  a row in the audit log
```

**Why it's built in separate pieces.** Each station can be checked, fixed, or
replaced without disturbing the others. The scoring rules don't know what a PDF
is. The PDF writer doesn't know what a score means. That separation is why a
change to how the report *looks* cannot quietly break whether the report is
*right* — and it's why the app can swap the AI for built-in rules mid-run and
still produce the same report.

**Two reports, one pipeline.** The same run produces either the full ~26-page
evidence report or a **one-page decision sheet** for someone approving a
purchase. Set `report_style` to `full` or `one_page`.

### The technical version

Ports and adapters (hexagonal). A pure core, with everything that touches the
outside world as a swappable adapter around it.

```
                 ┌─────────────────────────────────────────────┐
   INPUT         │                  CORE (pure)                 │        OUTPUT
                 │                                              │
  PDF ─┐         │   parsing/  →  domain/  →  reporting inputs  │        ┌─ PDF report
  DOCX ─┼─ extraction/ ─────────────►  models / scoring /  ─────┼─ reporting/ ─► (full or 1-page)
  TXT ─┘  (Extractor port)         impact / policy / verdict   │  (ReportRenderer port)
                 │                       ▲                      │
                 │                       │ reads               │        ┌─ risk verdict
                 │                  reference/ (wcag.json)      ├─ ai/ ──► (Bedrock, or the
                 │                                              │  (RiskAssessor  offline rules)
                 │                                              ├─ audit/ ─► CSV row
                 └───────────────────────┬──────────────────────┘  (AuditLog port)
                                         │ orchestrated by
                              service.py  →  cli.py / ui.gui (adapters)
                                         │ configured by
                        config/ (settings.json: identity + grading + Bedrock)
```

**The dependency rule: arrows point inward.** `domain/` depends on nothing.
Everything else depends on `domain/`. `service.py` wires them together; `cli.py`
and `ui/gui/` are the outermost layer.

| Package | Job |
|---|---|
| `domain/` | Models, scoring, impact, grading policy, the five verdicts. Pure — no I/O, no libraries. |
| `extraction/` | File bytes → text and tables. One adapter per format. |
| `parsing/` | Text and tables → a `VPATDocument`. The hardest part of the app. |
| `reference/` | WCAG knowledge as data (`wcag.json`) — descriptions and workarounds. |
| `reporting/` | A review → a PDF. Two renderers behind one port. |
| `ai/` | A review → a verdict. Where the network lives, which is why it's a boundary. |
| `audit/` | A review → a CSV row. |
| `config/` | Everything a user can edit. |
| `service.py` | Orchestration. Builds records; never decides to reach for a network. |
| `ui/gui/`, `cli.py` | The adapters people actually use. |

**Why the AI is a boundary and not the brain.** The AI produces one thing — the
verdict — and the app is designed to lose it gracefully. `service.assess_result`
never raises: a failed call, or an answer that can't be read as one of the five
categories, records an honest non-verdict and the built-in rules take over. The
report is always produced. The rule throughout the AI layer is **reject, never
repair**: an unrecognized category is refused rather than mapped to the closest
one, because a verdict nobody can distinguish from a real one is worse than no
verdict.

---

## Settings

`settings.json` sits next to the app. It holds who you are, the grading rules,
and the AI configuration.

| Setting | Does |
|---|---|
| `org_name`, `reviewer_name`, `logo_path` | Branding on the report. |
| `report_style` | `one_page` (decision sheet) or `full` (~26 pages of evidence). |
| `threshold` | The compliance bar. Default `90`. |
| `use_ai` | `false` makes the app fully offline. |
| `bedrock_model_id`, `bedrock_region` | Which AI model, and where. |
| `audit_log_enabled`, `audit_log_path` | The CSV log. |

Grading rules — what counts as supported, what's excluded, the score bands — are
editable too, via the Settings dialog, `vpat-review policy set`, or the file.

### AI credentials

> **Never put a key in `settings.json`.** It's tracked in git and ships next to
> the app, so anything in it is effectively public. There is deliberately no
> setting a key fits in, and the app ignores one if you add it by hand.

| How | Where |
|---|---|
| AWS SSO (recommended) | `aws configure sso`, then `"bedrock_profile": "your-profile"` |
| Environment variable | `AWS_BEARER_TOKEN_BEDROCK` or `VPAT_BEDROCK_API_KEY` |
| Shared key file | `bedrock_api_key.txt` next to `settings.json` (gitignored) |

**Model ids need care.** Some Bedrock models require a cross-region *inference
profile* id (`us.anthropic.…`) and reject the plain catalog id — and a wrong id
fails *silently*: every report quietly falls back to the offline verdict. Get ids
from `aws bedrock list-inference-profiles`, and confirm a real review shows
`verdict_source = ai` in the audit log.

---

## For developers

**Read [`CLAUDE.md`](CLAUDE.md) before changing anything.** It's the map and the
rulebook — the "do not break" list and the reasoning behind each one.

### The gates — all must pass before you commit

```bash
ruff check .                    # lint
ruff format .                   # format
mypy                            # strict type-checking
python -m pytest -q             # the whole suite
python make_demo.py             # must print: Score: 72 … Validation: OK
python tools/corpus_report.py --check   # the parser vs real vendor VPATs
```

That **`Score: 72 … Validation: OK`** line is the canary for the entire scoring
pipeline. If it changes, you changed scoring — make sure that was intentional.

`corpus_report.py` is the other half of the net, and the more truthful half: the
unit tests only know the shapes we thought of; the corpus knows what vendors
actually ship.

### The rules that matter most

1. **Never invent a parsed row.** If the document doesn't state a status, report
   none. A wrong status is worse than a missing one — the report states it as
   fact and nobody downstream can tell.
2. **Never invent a verdict.** Same rule, higher stakes.
3. **The domain layer stays pure.** No PDF libraries, no filesystem, no network.
4. **Never change the parser without running the real corpus.**
5. **Escape anything the app didn't author** before it reaches the PDF or the
   CSV. Vendor text is untrusted input in both.

### Project layout

| Path | What it is |
|---|---|
| `src/vpat_reviewer/` | The package. New code goes here. |
| `tests/` | Mirrors the package. |
| `docs/` | Design notes, the model evaluation, real vendor VPATs. |
| `tools/corpus_report.py` | The parser scoreboard. Dev-only. |
| `run_app.py` | Launches the GUI; the entry point the `.exe` is built from. |
| `make_demo.py` | The behavior anchor. |

---

## Building the app to share

```bash
build_exe.bat                        # → dist\VPAT_Reviewer.exe
dist\VPAT_Reviewer.exe --selftest    # verify any build
```

Optionally open `installer.iss` in Inno Setup and click Compile for a
single-click installer. Full details in
[`BUILD_INSTRUCTIONS.md`](BUILD_INSTRUCTIONS.md).

`--selftest` confirms the bundled data loads. It does **not** confirm the AI
works — for that, generate one real report and check `verdict_source` in the
audit log.

---

## Where to read more

| Document | For |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **Anyone changing the code.** The map + the rulebook. |
| [`docs/architecture.md`](docs/architecture.md) | Design rationale and project history. |
| [`docs/extending.md`](docs/extending.md) | Recipes: new format, new report, new AI provider. |
| [`BUILD_INSTRUCTIONS.md`](BUILD_INSTRUCTIONS.md) | Building the exe and installer. |
| `INSTALL_INSTRUCTIONS.txt` | Hand this to end users. |
