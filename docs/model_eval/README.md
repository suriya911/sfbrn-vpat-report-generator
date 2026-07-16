# Bedrock model evaluation

Which Bedrock model should the AI review step use? These files answer that with
measured data rather than opinion: every candidate model was sent the *identical*
prompt (the parsed VPAT JSON built by `ai/review.py::build_prompt`) and its reply
was scored on JSON validity, depth, cost, latency, and verdict agreement.

## Start here

| File | What it is |
|---|---|
| **`MULTIDOC_COMPARISON.md`** | **The one to read.** 59 models × 5 real vendor VPATs = 295 runs. Top 10, per-doc consensus, verdict matrix, all models. |
| `per_doc/*.md` | One report per PDF (Cornerstone, Atrium Connect, Canvas, iCIMS, H5P), each with that document's top 10 + all models. |
| `MODEL_COMPARISON.md` | Earlier single-document deep dive — 67 models against Cornerstone only, including the 8 that failed and why. |
| `multidoc_results.json` | Raw data behind the multi-doc run: one record per (model, document). |
| `bench_results.json` | Raw data behind the single-doc run, including each model's full reply text. |
| `raw_outputs/*.txt` | Verbatim reply from each model in the single-doc run, for eyeballing quality yourself. |

## Headline findings

- **Highest quality:** Claude Sonnet 4.5 — avg quality 94.1/100, but ~$0.059/doc.
- **Best value:** Nova 2 Lite — avg quality 84.9, **$0.00066/doc**, and it matched
  the consensus verdict on all 5 documents.
- **Best quality-per-dollar:** Kimi K2.5 (89.5 quality, $0.0079/doc) and
  MiniMax M2.1 (85.6, $0.0048/doc).
- **The current default, Claude Haiku 4.5, over-flags.** It returned `Need TAAP`
  for all five documents — including the milder iCIMS and H5P that most models
  rated `Minor Issue` — so its agreement with consensus is only 40%. It is
  consistent, but consistently harsh. Worth revisiting before the model choice is
  locked in (`settings.json` → `bedrock_model_id`).

## How the numbers were produced

- **Costs are estimates.** Bedrock exposes no pricing API, so per-model
  input/output prices were entered by hand and multiplied by the exact token
  counts Bedrock returned. Token counts are real; dollar figures are arithmetic
  on hand-entered rates and should be re-checked against current AWS pricing
  before anyone quotes them.
- **Agreement is a proxy for reliability, not ground truth.** Nobody hand-labeled
  the correct verdict for these five VPATs. "Consensus" is simply what most models
  concluded for a given document, so agreement measures *does this model track the
  crowd*, not *is this model right*. A model could in principle beat the crowd and
  score badly here.
- **Quality is a heuristic**, not a human read: valid JSON parse + rationale depth
  + recommendation count + summary richness + consensus agreement.

To re-run or extend the benchmark, the driver scripts are not committed (they were
throwaway); the reusable pieces they call are `service.analyze()`,
`ai.review.build_prompt()`, and `ai.review.parse_ai_reply()`, driven against
`bedrock-runtime.converse` with the API key from `ai/bedrock.py`.
