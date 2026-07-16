# Bedrock Model Comparison — Multi-Document (5 VPATs)

**Generated:** 2026-07-15 23:42  
**Models:** 59  ·  **Documents:** 5  ·  **Total runs:** 295

Every model was run against all five real vendor VPATs with the identical prompt. This tests **consistency** (does a model agree with the crowd on each doc?) and **average cost/quality** across documents — a better basis for selection than a single doc. Token counts are exact; **costs are estimates** (Bedrock has no pricing API).

## Per-document consensus verdict

What most models concluded for each VPAT (the crowd 'answer key').

| Document | Consensus verdict |
|---|---|
| Cornerstone | **Need TAAP** |
| Atrium Connect | **Need TAAP** |
| Canvas | **Needs Manual Review** |
| iCIMS | **Minor Issue** |
| H5P | **Minor Issue** |

## Quick picks (across all 5 docs)

- **Best value:** Nova 2 Lite — avg quality 84.9, $0.00066/doc, 100% agreement
- **Most consistent** (agrees with consensus every doc): Palmyra X5 — 100% agreement, avg quality 85.2
- **Highest avg quality:** Claude Sonnet 4.5 — 94.1/100

## Top 10 models (averaged over 5 docs)

| # | Model | Provider | Avg quality | Agreement | Avg cost/doc | 5-doc total | Avg latency |
|---|-------|----------|------:|------:|------:|------:|----:|
| 1 | **Claude Sonnet 4.5** | Anthropic | 94.1 | 80% | $0.05883 | $0.29414 | 40.9s |
| 2 | **Claude Sonnet 4.6** | Anthropic | 94.0 | 60% | $0.06539 | $0.32696 | 45.4s |
| 3 | **Claude Opus 4.5** | Anthropic | 89.6 | 80% | $0.08222 | $0.41111 | 28.6s |
| 4 | **Kimi K2.5** | Moonshot | 89.5 | 80% | $0.00793 | $0.03964 | 10.3s |
| 5 | **Claude Opus 4.8** | Anthropic | 88.1 | 60% | $0.11230 | $0.56148 | 26.1s |
| 6 | **Claude Opus 4.7** | Anthropic | 87.2 | 60% | $0.10700 | $0.53501 | 21.1s |
| 7 | **Claude Haiku 4.5** | Anthropic | 86.6 | 40% | $0.02378 | $0.11890 | 26.0s |
| 8 | **Claude Opus 4.6** | Anthropic | 86.0 | 80% | $0.07850 | $0.39252 | 26.4s |
| 9 | **MiniMax M2.1** | MiniMax | 85.6 | 80% | $0.00484 | $0.02420 | 18.0s |
| 10 | **Palmyra X5** | Writer | 85.2 | 100% | $0.03074 | $0.15371 | 13.0s |

*Agreement = % of docs where the model matched that doc's consensus verdict.

## Verdict matrix — top 15 models × 5 docs

Shows how consistently each model tracks the per-doc consensus.

| Model | Cornerstone | Atrium Connect | Canvas | iCIMS | H5P |
|---|---|---|---|---|---|
| Claude Sonnet 4.5 | Need TAAP | Need TAAP | Need TAAP | Minor Issue | Minor Issue |
| Claude Sonnet 4.6 | Need TAAP | Need TAAP | Need TAAP | Needs Manual Review | Minor Issue |
| Claude Opus 4.5 | Need TAAP | Need TAAP | Need TAAP | Minor Issue | Minor Issue |
| Kimi K2.5 | Need TAAP | Need TAAP | Need TAAP | Minor Issue | Minor Issue |
| Claude Opus 4.8 | Need TAAP | Need TAAP | Need TAAP | Need TAAP | Minor Issue |
| Claude Opus 4.7 | Need TAAP | Need TAAP | Need TAAP | Need TAAP | Minor Issue |
| Claude Haiku 4.5 | Need TAAP | Need TAAP | Need TAAP | Need TAAP | Need TAAP |
| Claude Opus 4.6 | Need TAAP | Need TAAP | Need TAAP | Minor Issue | Minor Issue |
| MiniMax M2.1 | Need TAAP | Need TAAP | Need TAAP | Minor Issue | Minor Issue |
| Palmyra X5 | Need TAAP | Need TAAP | Needs Manual Review | Minor Issue | Minor Issue |
| Nova 2 Lite | Need TAAP | Need TAAP | Needs Manual Review | Minor Issue | Minor Issue |
| Claude Sonnet 5 | Need TAAP | Need TAAP | Need TAAP | Need TAAP | Needs Manual Review |
| GLM 5 | Need TAAP | Need TAAP | Needs Manual Review | Minor Issue | Minor Issue |
| Qwen3 VL 235B | Need TAAP | Need TAAP | Needs Manual Review | Needs Manual Review | Minor Issue |
| NVIDIA Nemotron Super 3 120B | Need TAAP | Need TAAP | Needs Manual Review | Needs Manual Review | Minor Issue |
| **CONSENSUS** | **Need TAAP** | **Need TAAP** | **Needs Manual Review** | **Minor Issue** | **Minor Issue** |

## All models (aggregate)

| Model | Provider | Docs ok | Avg quality | Agreement | Avg cost/doc | Avg latency |
|-------|----------|:---:|------:|------:|------:|----:|
| Claude Sonnet 4.5 | Anthropic | 5/5 | 94.1 | 80% | $0.05883 | 40.9s |
| Claude Sonnet 4.6 | Anthropic | 5/5 | 94.0 | 60% | $0.06539 | 45.4s |
| Claude Opus 4.5 | Anthropic | 5/5 | 89.6 | 80% | $0.08222 | 28.6s |
| Kimi K2.5 | Moonshot | 5/5 | 89.5 | 80% | $0.00793 | 10.3s |
| Claude Opus 4.8 | Anthropic | 5/5 | 88.1 | 60% | $0.11230 | 26.1s |
| Claude Opus 4.7 | Anthropic | 5/5 | 87.2 | 60% | $0.10700 | 21.1s |
| Claude Haiku 4.5 | Anthropic | 5/5 | 86.6 | 40% | $0.02378 | 26.0s |
| Claude Opus 4.6 | Anthropic | 5/5 | 86.0 | 80% | $0.07850 | 26.4s |
| MiniMax M2.1 | MiniMax | 5/5 | 85.6 | 80% | $0.00484 | 18.0s |
| Palmyra X5 | Writer | 5/5 | 85.2 | 100% | $0.03074 | 13.0s |
| Nova 2 Lite | Amazon | 5/5 | 84.9 | 100% | $0.00066 | 5.3s |
| Claude Sonnet 5 | Anthropic | 5/5 | 83.2 | 40% | $0.08602 | 33.1s |
| GLM 5 | Z.AI | 5/5 | 82.9 | 100% | $0.00675 | 14.6s |
| Qwen3 VL 235B | Qwen | 5/5 | 82.5 | 80% | $0.00648 | 12.8s |
| NVIDIA Nemotron Super 3 120B | NVIDIA | 5/5 | 82.4 | 80% | $0.00681 | 137.2s |
| Qwen3 235B A22 | Qwen | 5/5 | 81.9 | 80% | $0.00653 | 9.1s |
| Nemotron Nano 3 30B | NVIDIA | 5/5 | 80.9 | 40% | $0.00189 | 4.5s |
| MiniMax M2.5 | MiniMax | 5/5 | 80.5 | 60% | $0.00480 | 18.6s |
| Qwen3 Coder 480B | Qwen | 5/5 | 79.9 | 100% | $0.01023 | 6.5s |
| Qwen3 Coder 30B | Qwen | 5/5 | 79.6 | 80% | $0.00211 | 3.5s |
| Claude Opus 4.1 | Anthropic | 5/5 | 78.9 | 80% | $0.20830 | 57.1s |
| Qwen3 Next 80B | Qwen | 5/5 | 78.4 | 40% | $0.00342 | 11.7s |
| DeepSeek V3.2 | DeepSeek | 5/5 | 77.6 | 60% | $0.00264 | 15.4s |
| Mistral Large 3 | Mistral | 5/5 | 77.2 | 60% | $0.02264 | 7.4s |
| GLM 4.7 | Z.AI | 5/5 | 76.7 | 80% | $0.00679 | 13.4s |
| GPT OSS Safeguard 20b | OpenAI | 5/5 | 76.5 | 60% | $0.00113 | 19.9s |
| DeepSeek V3.1 | DeepSeek | 5/5 | 76.5 | 80% | $0.00582 | 4.2s |
| gpt-oss-20b | OpenAI | 4/5 | 75.9 | 50% | $0.00120 | 4.3s |
| Gemma 3 27B | Google | 5/5 | 75.1 | 80% | $0.00205 | 11.6s |
| gpt-oss-120b | OpenAI | 5/5 | 74.8 | 40% | $0.00204 | 11.7s |
| GLM 4.7 Flash | Z.AI | 5/5 | 74.2 | 60% | $0.00108 | 4.8s |
| Devstral 2 123B | Mistral | 5/5 | 73.5 | 80% | $0.02030 | 13.0s |
| Nova Pro | Amazon | 5/5 | 72.2 | 100% | $0.00830 | 4.1s |
| Kimi K2 Thinking | Moonshot | 4/5 | 71.2 | 50% | $0.01320 | 27.7s |
| Mistral Large 2 (2407) | Mistral | 5/5 | 71.2 | 80% | $0.02298 | 18.8s |
| Palmyra X4 | Writer | 5/5 | 71.0 | 80% | $0.02714 | 10.1s |
| GPT OSS Safeguard 120b | OpenAI | 5/5 | 70.7 | 40% | $0.00212 | 39.8s |
| Gemma 3 12B | Google | 5/5 | 70.2 | 60% | $0.00102 | 6.5s |
| Magistral Small | Mistral | 5/5 | 70.0 | 80% | $0.00508 | 8.8s |
| Pixtral Large (25.02) | Mistral | 5/5 | 69.4 | 60% | $0.02357 | 11.8s |
| Llama 4 Scout | Meta | 5/5 | 67.9 | 80% | $0.00168 | 3.6s |
| Qwen3 32B (dense) | Qwen | 5/5 | 67.7 | 60% | $0.00198 | 123.8s |
| Nemotron Nano 12B | NVIDIA | 5/5 | 67.6 | 40% | $0.00086 | 3.5s |
| Llama 3.3 70B | Meta | 5/5 | 67.4 | 80% | $0.00614 | 3.5s |
| Mistral Large (2402) | Mistral | 5/5 | 67.1 | 60% | $0.04522 | 13.4s |
| Llama 4 Maverick | Meta | 5/5 | 66.7 | 60% | $0.00233 | 2.4s |
| DeepSeek R1 | DeepSeek | 5/5 | 66.3 | 40% | $0.01822 | 9.5s |
| Nova Micro | Amazon | 5/5 | 65.3 | 60% | $0.00035 | 5.2s |
| Nova Lite | Amazon | 5/5 | 64.9 | 60% | $0.00061 | 3.6s |
| Llama 3.1 70B | Meta | 5/5 | 64.7 | 100% | $0.00609 | 39.6s |
| Llama 3.1 8B | Meta | 5/5 | 64.5 | 100% | $0.00185 | 2.5s |
| Gemma 3 4B | Google | 5/5 | 64.3 | 40% | $0.00052 | 3.6s |
| Mixtral 8x7B | Mistral | 5/5 | 63.5 | 40% | $0.00468 | 15.4s |
| Nemotron Nano 9B | NVIDIA | 5/5 | 63.3 | 40% | $0.00072 | 9.4s |
| Claude 3 Haiku | Anthropic | 5/5 | 60.4 | 60% | $0.00305 | 6.2s |
| Mistral 7B Instruct | Mistral | 5/5 | 59.0 | 40% | $0.00156 | 13.2s |
| Ministral 14B 3.0 | Mistral | 4/5 | 38.8 | 25% | $0.00153 | 9.8s |
| Ministral 3B | Mistral | 5/5 | 38.0 | 20% | $0.00042 | 5.4s |
| Ministral 3 8B | Mistral | 5/5 | 38.0 | 20% | $0.00116 | 19.7s |

## Notes

- Raw per-(model,doc) data: `docs/model_eval/multidoc_results.json`.
- 'Agreement' rewards matching the crowd per document; it is a proxy for reliability, not ground truth (no human-labeled verdicts).
- Single-document deep-dive (67 models, one doc) is in `MODEL_COMPARISON.md`.
