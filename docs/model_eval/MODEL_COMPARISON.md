# Bedrock Model Comparison — VPAT Accessibility Review

**Test document:** Cornerstone Learning Management and Core Platform (Core App). This is  
**Generated:** 2026-07-15 23:18  
**Models tested:** 67  ·  succeeded: 59  ·  failed/unsupported: 8  
**Consensus verdict** (most models agreed): **Need TAAP**

Each model received the *identical* prompt (the app's `prompt.txt` + the parsed VPAT JSON) via the Bedrock Converse API. Token counts are exact (from the API); **dollar costs are estimates** — Bedrock prices are not exposed by an API, so verify against the AWS Bedrock pricing page. Quality is a heuristic (valid JSON + completeness + agreement with the consensus verdict), not a substitute for reading the outputs in `docs/model_eval/raw_outputs/`.

## Quick picks

- **Best value (quality + low cost):** Nova 2 Lite — quality 91/100, $0.00075/run, 6.51s
- **Cheapest that worked:** Nova Micro — $0.00043/run, quality 73/100
- **Fastest:** Llama 4 Maverick — 2.21s, quality 71/100
- **Highest quality:** Claude Sonnet 4.6 — quality 100/100

## Top 10 models

Ranked by response quality, then by cost (cheaper wins ties).

| # | Model | Provider | Verdict | Quality /100 | Cost/run (est) | Latency | In→Out tok | Value* |
|---|-------|----------|---------|------:|------:|----:|----:|----:|
| 1 | **Claude Sonnet 4.6** | Anthropic | Need TAAP | 100 | $0.07506 | 49.05s | 11510→2702 | 13.3 |
| 2 | **Claude Opus 4.8** | Anthropic | Need TAAP | 98 | $0.13095 | 27.17s | 14890→2260 | 7.5 |
| 3 | **Claude Opus 4.5** | Anthropic | Need TAAP | 97 | $0.08965 | 26.67s | 11510→1284 | 10.8 |
| 4 | **Claude Sonnet 4.5** | Anthropic | Need TAAP | 96 | $0.06450 | 39.72s | 11510→1998 | 14.9 |
| 5 | **Claude Opus 4.7** | Anthropic | Need TAAP | 96 | $0.12582 | 23.55s | 14895→2054 | 7.6 |
| 6 | **Claude Opus 4.6** | Anthropic | Need TAAP | 95 | $0.09273 | 69.94s | 11510→1407 | 10.2 |
| 7 | **Nemotron Nano 3 30B** | NVIDIA | Need TAAP | 93 | $0.00215 | 3.87s | 9936→1093 | 432.6 |
| 8 | **MiniMax M2.1** | MiniMax | Need TAAP | 93 | $0.00519 | 16.02s | 9459→1959 | 179.2 |
| 9 | **NVIDIA Nemotron Super 3 120B** | NVIDIA | Need TAAP | 93 | $0.00822 | 10.54s | 9936→1254 | 113.1 |
| 10 | **Claude Haiku 4.5** | Anthropic | Need TAAP | 93 | $0.02870 | 32.8s | 11510→3438 | 32.4 |

*Value = quality per US-cent (higher = more quality per dollar).

## Batch comparison — new models vs the original run

| | Original list (batch 1) | New models (batch 2) |
|---|---|---|
| Models tested | 32 | 35 |
| Succeeded | 25 | 34 |
| All returned 'Need TAAP' | yes | n/a |
| Best new model | — | MiniMax M2.1 (quality 93, $0.00519) |

- New models that broke into the overall Top 10: **Nemotron Nano 3 30B, MiniMax M2.1, NVIDIA Nemotron Super 3 120B**.
- The consensus verdict is unchanged at **Need TAAP** after adding 34 more working models.

## All models tested (full results)

| Model | Provider | Batch | Status | Verdict | Quality | Cost/run (est) | Latency | In→Out tok |
|-------|----------|:---:|--------|---------|------:|------:|----:|----:|
| Claude Sonnet 4.6 | Anthropic | 1 | ok | Need TAAP | 100 | $0.07506 | 49.05s | 11510→2702 |
| Claude Opus 4.8 | Anthropic | 1 | ok | Need TAAP | 98 | $0.13095 | 27.17s | 14890→2260 |
| Claude Opus 4.5 | Anthropic | 1 | ok | Need TAAP | 97 | $0.08965 | 26.67s | 11510→1284 |
| Claude Opus 4.7 | Anthropic | 1 | ok | Need TAAP | 96 | $0.12582 | 23.55s | 14895→2054 |
| Claude Sonnet 4.5 | Anthropic | 1 | ok | Need TAAP | 96 | $0.06450 | 39.72s | 11510→1998 |
| Claude Opus 4.6 | Anthropic | 1 | ok | Need TAAP | 95 | $0.09273 | 69.94s | 11510→1407 |
| Claude Haiku 4.5 | Anthropic | 1 | ok | Need TAAP | 93 | $0.02870 | 32.8s | 11510→3438 |
| MiniMax M2.1 | MiniMax | 2 | ok | Need TAAP | 93 | $0.00519 | 16.02s | 9459→1959 |
| NVIDIA Nemotron Super 3 120B | NVIDIA | 2 | ok | Need TAAP | 93 | $0.00822 | 10.54s | 9936→1254 |
| Nemotron Nano 3 30B | NVIDIA | 2 | ok | Need TAAP | 93 | $0.00215 | 3.87s | 9936→1093 |
| Kimi K2.5 | Moonshot | 2 | ok | Need TAAP | 92 | $0.01054 | 13.43s | 9574→1919 |
| gpt-oss-120b | OpenAI | 2 | ok | Need TAAP | 92 | $0.00242 | 10.22s | 9516→1662 |
| Nova 2 Lite | Amazon | 1 | ok | Need TAAP | 91 | $0.00075 | 6.51s | 9466→748 |
| Palmyra X5 | Writer | 2 | ok | Need TAAP | 90 | $0.03635 | 14.74s | 9930→1152 |
| Qwen3 Next 80B | Qwen | 2 | ok | Need TAAP | 90 | $0.00392 | 10.88s | 9701→1120 |
| Claude Sonnet 5 | Anthropic | 1 | ok | Need TAAP | 89 | $0.09268 | 32.79s | 14890→3201 |
| DeepSeek V3.2 | DeepSeek | 1 | ok | Need TAAP | 89 | $0.00314 | 10.43s | 9690→1019 |
| MiniMax M2.5 | MiniMax | 2 | ok | Need TAAP | 89 | $0.00546 | 16.86s | 9459→2186 |
| Claude Opus 4.1 | Anthropic | 1 | ok | Need TAAP | 88 | $0.23895 | 217.26s | 11510→884 |
| Qwen3 235B A22 | Qwen | 2 | ok | Need TAAP | 88 | $0.00791 | 10.15s | 9701→1160 |
| Qwen3 Coder 30B | Qwen | 2 | ok | Need TAAP | 87 | $0.00240 | 3.16s | 9701→759 |
| Qwen3 VL 235B | Qwen | 2 | ok | Need TAAP | 86 | $0.00741 | 13.36s | 9701→884 |
| Mistral Large 3 | Mistral | 2 | ok | Need TAAP | 85 | $0.02780 | 7.44s | 9923→1326 |
| gpt-oss-20b | OpenAI | 2 | ok | Need TAAP | 85 | $0.00108 | 6.97s | 9516→1375 |
| GPT OSS Safeguard 20b | OpenAI | 2 | ok | Need TAAP | 84 | $0.00116 | 16.67s | 9516→1647 |
| Qwen3 Coder 480B | Qwen | 2 | ok | Need TAAP | 84 | $0.01181 | 6.44s | 9701→704 |
| Kimi K2 Thinking | Moonshot | 2 | ok | Need TAAP | 83 | $0.01371 | 26.65s | 9575→3186 |
| GLM 5 | Z.AI | 2 | ok | Need TAAP | 82 | $0.00775 | 9.17s | 9592→907 |
| Palmyra X4 | Writer | 2 | ok | Need TAAP | 82 | $0.03316 | 12.5s | 9721→886 |
| DeepSeek V3.1 | DeepSeek | 1 | ok | Need TAAP | 80 | $0.00676 | 5.0s | 9690→681 |
| GLM 4.7 | Z.AI | 2 | ok | Need TAAP | 80 | $0.00737 | 14.75s | 9592→732 |
| Mixtral 8x7B | Mistral | 2 | ok | Need TAAP | 80 | $0.00560 | 17.76s | 11606→540 |
| Devstral 2 123B | Mistral | 2 | ok | Need TAAP | 79 | $0.02373 | 14.79s | 9923→647 |
| Gemma 3 27B | Google | 1 | ok | Need TAAP | 79 | $0.00240 | 9.51s | 10774→618 |
| Gemma 3 4B | Google | 1 | ok | Need TAAP | 79 | $0.00063 | 4.49s | 10774→945 |
| Nemotron Nano 12B | NVIDIA | 2 | ok | Need TAAP | 79 | $0.00097 | 3.34s | 9935→590 |
| DeepSeek R1 | DeepSeek | 1 | ok | Need TAAP | 78 | $0.02161 | 10.66s | 9691→1579 |
| GLM 4.7 Flash | Z.AI | 2 | ok | Need TAAP | 78 | $0.00125 | 4.3s | 9592→971 |
| Gemma 3 12B | Google | 1 | ok | Need TAAP | 77 | $0.00120 | 7.53s | 10774→618 |
| Llama 4 Scout | Meta | 1 | ok | Need TAAP | 77 | $0.00201 | 4.99s | 9485→599 |
| Magistral Small | Mistral | 2 | ok | Need TAAP | 77 | $0.00599 | 10.06s | 9923→687 |
| Pixtral Large (25.02) | Mistral | 2 | ok | Need TAAP | 77 | $0.02749 | 10.12s | 11599→715 |
| Nova Lite | Amazon | 1 | ok | Need TAAP | 75 | $0.00074 | 3.4s | 10304→505 |
| Nova Pro | Amazon | 1 | ok | Need TAAP | 75 | $0.00970 | 4.74s | 10304→455 |
| Qwen3 32B (dense) | Qwen | 2 | ok | Need TAAP | 75 | $0.00229 | 3.84s | 9705→580 |
| Mistral Large 2 (2407) | Mistral | 2 | ok | Need TAAP | 73 | $0.02640 | 15.25s | 11599→534 |
| Nova Micro | Amazon | 1 | ok | Need TAAP | 73 | $0.00043 | 2.88s | 10304→482 |
| Claude 3 Haiku | Anthropic | 1 | ok | Need TAAP | 72 | $0.00361 | 6.56s | 11510→584 |
| Llama 3.1 70B | Meta | 1 | ok | Need TAAP | 72 | $0.00722 | 73.78s | 9572→456 |
| Llama 3.1 8B | Meta | 1 | ok | Need TAAP | 72 | $0.00219 | 2.79s | 9573→383 |
| Nemotron Nano 9B | NVIDIA | 2 | ok | Need TAAP | 72 | $0.00085 | 10.48s | 9932→1748 |
| Llama 4 Maverick | Meta | 1 | ok | Need TAAP | 71 | $0.00270 | 2.21s | 9485→435 |
| Llama 3.3 70B | Meta | 1 | ok | Need TAAP | 70 | $0.00723 | 4.14s | 9593→450 |
| GPT OSS Safeguard 120b | OpenAI | 2 | ok | Needs Manual Review | 68 | $0.00233 | 39.36s | 9516→1511 |
| Mistral Large (2402) | Mistral | 2 | ok | Need TAAP | 68 | $0.05260 | 14.52s | 11600→517 |
| Mistral 7B Instruct | Mistral | 2 | ok | Needs Manual Review | 65 | $0.00192 | 19.05s | 11606→910 |
| Ministral 14B 3.0 | Mistral | 2 | ok | Needs Manual Review | 35 | $0.00194 | 13.22s | 9923→3042 |
| Ministral 3 8B | Mistral | 2 | ok | Needs Manual Review | 35 | $0.00130 | 12.67s | 9923→3048 |
| Ministral 3B | Mistral | 2 | ok | Needs Manual Review | 35 | $0.00052 | 7.71s | 9923→3133 |
| Claude 3 Sonnet | Anthropic | 1 | ERROR | — | 0 | — | 0.15s | 0→0 |
| Claude Sonnet 4 | Anthropic | 1 | ERROR | — | 0 | — | 0.24s | 0→0 |
| Command R | Cohere | 1 | ERROR | — | 0 | — | 0.2s | 0→0 |
| Command R+ | Cohere | 1 | ERROR | — | 0 | — | 0.19s | 0→0 |
| Llama 3 70B | Meta | 1 | ERROR | — | 0 | — | 0.19s | 0→0 |
| Llama 3 8B | Meta | 1 | ERROR | — | 0 | — | 0.61s | 0→0 |
| MiniMax M2 | MiniMax | 2 | no-json | — | 0 | $0.00763 | 32.4s | 9443→4000 |
| Nova Premier | Amazon | 1 | ERROR | — | 0 | — | 0.17s | 0→0 |

## Failed / unsupported

- **Nova Premier** (us.amazon.nova-premier-v1:0): An error occurred (ResourceNotFoundException) when calling the Converse operation: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 
- **Claude 3 Sonnet** (us.anthropic.claude-3-sonnet-20240229-v1:0): An error occurred (ResourceNotFoundException) when calling the Converse operation: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 
- **Claude Sonnet 4** (us.anthropic.claude-sonnet-4-20250514-v1:0): An error occurred (ResourceNotFoundException) when calling the Converse operation: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 
- **Command R** (cohere.command-r-v1:0): An error occurred (ResourceNotFoundException) when calling the Converse operation: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 
- **Command R+** (cohere.command-r-plus-v1:0): An error occurred (ResourceNotFoundException) when calling the Converse operation: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 
- **Llama 3 8B** (meta.llama3-8b-instruct-v1:0): An error occurred (ValidationException) when calling the Converse operation: The model returned the following errors: This model's maximum context length is 8192 tokens. Please reduce the length of th
- **Llama 3 70B** (meta.llama3-70b-instruct-v1:0): An error occurred (ValidationException) when calling the Converse operation: The model returned the following errors: This model's maximum context length is 8192 tokens. Please reduce the length of th
- **MiniMax M2** (minimax.minimax-m2): returned no parseable JSON

## Notes

- Full raw model outputs are saved per model in `docs/model_eval/raw_outputs/` and the structured data in `docs/model_eval/bench_results.json` (extensible — future model runs append here).
- Pricing is estimated per model (USD per 1M input/output tokens) and may be stale; the exact token counts let you recompute cost with current AWS prices.
- 'Quality' rewards a valid strict-JSON reply, a filled summary/rationale/recommendations, and agreement with the consensus verdict. Read the raw outputs before a final choice.
