# Sample VPATs — one per verdict

Five sample VPAT documents, each crafted to land in a different review verdict.
Use them to demo the app, to test the UI, or as fixtures for an AI integration.

Each `<case>.txt` is a plain-text ACR the app can parse. Each
`<case>.expected.json` is the **machine-readable result** the pipeline produces
for that document (the same shape `service.write_json()` writes at runtime), plus
two extra keys — `recommended_answers` and `expected_verdict` — so an automated
consumer can assert the end-to-end outcome.

## The five cases

| File | Product | Score | AA barriers | Recommended answers | Verdict |
|---|---|---|---|---|---|
| `good_to_go.txt` | Northstar Docs | 100% | 0 | small team · no limit · low legal · individual | **Good to Go** |
| `minor_issue.txt` | BrightForms | 80% | 2 | small team · limits some · low legal · department | **Minor Issue** |
| `needs_manual_review.txt` | Cascade Analytics | 60% | 4 | small team · limits some · low legal · department | **Needs Manual Review** |
| `need_taap.txt` | Adobe Audience Manager | 65% | 7 | campus-wide · limits some · **high** legal · campus-wide | **Need TAAP** |
| `deny.txt` | LegacyPortal Suite | 30% | 14 | campus-wide · **denies access** · high legal · campus-wide | **Deny** |

The verdict depends on **both** the parsed score and the impact answers you pick
in the app. The "Recommended answers" column is what reproduces the target
verdict; the samples are also designed so their own barrier counts push the
impact rating in the intended direction (e.g. the Deny and TAAP docs contain
fully-unsupported criteria, which flag High impact regardless of answers).

## How the verdict is decided

`classify_report(score, impact_level, barriers, access, good_cut=90)` — checked
top-down, first match wins:

1. score is `None` → **Needs Manual Review**
2. High impact **and** access = "denies access" → **Deny**
3. High impact **and** score < 50 → **Deny**
4. High impact (score ≥ 50) → **Need TAAP**
5. score ≥ `good_cut` (Settings threshold, default 90) **and** 0 barriers → **Good to Go**
6. score ≥ 70 → **Minor Issue**
7. otherwise → **Needs Manual Review**

## AI integration

The JSON files are the integration contract. An AI extraction layer only has to
produce the same normalized shape — then scoring, impact, and classification run
unchanged on top of it:

```json
{
  "product_name": "...", "vendor_name": "...", "vendor_report_date_raw": "...",
  "standards_reviewed": ["WCAG 2.1 Level AA", "..."],
  "score": 65, "supported": 13, "reviewable_total": 20,
  "impact_level": "High",
  "barriers": ["1.4.3", "1.4.10", "..."],
  "criteria": [{"id": "1.4.3", "level": "AA", "status": "Partially Supports", "section": "wcag"}]
}
```

Two ways to plug AI in without touching the domain core:

- **AI as an extractor** — have the model read a messy PDF/DOCX and emit the
  `criteria` list (id · level · status · remarks). Feed those into
  `VPATDocument`; `compliance_score`, `calculate_impact`, and `classify_report`
  do the rest. This keeps scoring deterministic and auditable.
- **AI as a summarizer** — after the pipeline runs, hand the JSON above to the
  model to draft the plain-language review notes shown in the side panel.

`status` values are the five canonical ones: `Supports`, `Partially Supports`,
`Does Not Support`, `Not Applicable`, `Not Evaluated`. Keep an AI mapped onto
those and the whole scoring/verdict path stays stable.

## Regenerating

These files are generated. To rebuild and re-verify all five:

```
python samples/build_verdict_samples.py
```

It writes the `.txt` + `.expected.json` pairs and prints a pass/fail line per
case (asserting each still lands in its target verdict).
