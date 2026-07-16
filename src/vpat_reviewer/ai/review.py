"""Turn a parsed VPAT into an AI-authored verdict + narrative via Bedrock.

Flow:  parsed review -> JSON payload -> prompt.txt -> Bedrock -> JSON reply
       -> :class:`AIReview`  (verdict, impact level, rationale, summary, recs).

The model is asked to return a small JSON object (see ``prompt.txt``). Parsing is
deliberately tolerant — the model text is scanned for the first balanced ``{...}``
block — and every field is validated, so a malformed reply degrades to
``parsed_ok=False`` rather than crashing the pipeline. The caller then falls back
to the deterministic classifier.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vpat_reviewer.ai.bedrock import BedrockConfig, invoke
from vpat_reviewer.service import ReviewResult, to_dict

logger = logging.getLogger(__name__)

# The five verdict folders the app files reports into. Bedrock must pick one.
VERDICTS = ("Good to Go", "Minor Issue", "Needs Manual Review", "Need TAAP", "Deny")
_IMPACT_LEVELS = ("Low", "Medium", "High")
FALLBACK_VERDICT = "Needs Manual Review"

# The prompt's rubric uses its own category labels; map them onto the folders.
# Keys are lowercased. Covers both the rubric names (gtg, minor changes, denied)
# and the folder names themselves, plus common shorthands.
_VERDICT_ALIASES = {
    "gtg": "Good to Go",
    "good to go": "Good to Go",
    "good": "Good to Go",
    "minor changes": "Minor Issue",
    "minor change": "Minor Issue",
    "minor issue": "Minor Issue",
    "minor": "Minor Issue",
    "needs manual review": "Needs Manual Review",
    "manual review": "Needs Manual Review",
    "need taap": "Need TAAP",
    "taap": "Need TAAP",
    "denied": "Deny",
    "deny": "Deny",
}

# If the prompt contains one of these tokens it is replaced with the VPAT JSON;
# otherwise the JSON is appended under a header. Either way the model sees data.
PAYLOAD_TOKENS = ("{{vpat_acr_content}}", "{{VPAT_JSON}}")


@dataclass
class AIReview:
    verdict: str
    impact_level: str
    rationale: list[str]
    summary: str
    recommendations: list[str] = field(default_factory=list)
    raw_text: str = ""
    parsed_ok: bool = False


def _project_root() -> Path:
    # src/vpat_reviewer/ai/review.py -> parents[3] == the project root.
    return Path(__file__).resolve().parents[3]


def prompt_path() -> Path:
    """Where the Bedrock prompt lives. Override with ``VPAT_PROMPT_PATH``."""
    override = os.environ.get("VPAT_PROMPT_PATH")
    return Path(override) if override else _project_root() / "prompt.txt"


def load_prompt() -> str:
    p = prompt_path()
    if not p.exists():
        raise FileNotFoundError(f"Prompt file not found: {p}")
    return p.read_text(encoding="utf-8")


def build_prompt(result: ReviewResult) -> str:
    """Combine the user's prompt template with the parsed VPAT JSON payload."""
    payload = json.dumps(to_dict(result), indent=2, ensure_ascii=False)
    template = load_prompt()
    for token in PAYLOAD_TOKENS:
        if token in template:
            return template.replace(token, payload)
    return f"{template.rstrip()}\n\n--- VPAT DATA (JSON) ---\n{payload}\n"


def _extract_json(text: str) -> dict[str, Any] | None:
    """Return the first balanced ``{...}`` object parsed from ``text``, or None."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blob = text[start : i + 1]
                    try:
                        parsed = json.loads(blob)
                    except json.JSONDecodeError:
                        break  # try the next '{' after this start
                    return parsed if isinstance(parsed, dict) else None
        start = text.find("{", start + 1)
    return None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _match_verdict(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in _VERDICT_ALIASES:
        return _VERDICT_ALIASES[v]
    # tolerate embedded phrasings ("category: Need TAAP", "denied — ...")
    for alias, canonical in _VERDICT_ALIASES.items():
        if alias in v:
            return canonical
    return FALLBACK_VERDICT


def _match_impact(value: Any) -> str:
    """Map the rubric's risk_level onto the report's Low/Medium/High impact."""
    v = str(value or "").strip().lower()
    if "critical" in v:
        return "High"
    for level in _IMPACT_LEVELS:
        if level.lower() in v:
            return level
    return "Medium"  # covers "Unknown" and anything unrecognized


def parse_ai_reply(raw: str) -> AIReview:
    """Map a raw Bedrock reply into a validated :class:`AIReview`."""
    data = _extract_json(raw)
    if data is None:
        logger.warning("Bedrock reply contained no parseable JSON object.")
        return AIReview(
            verdict=FALLBACK_VERDICT,
            impact_level="Medium",
            rationale=[],
            summary=raw.strip()[:1200],
            raw_text=raw,
            parsed_ok=False,
        )

    summary = str(
        data.get("reason") or data.get("summary") or data.get("executive_summary") or ""
    ).strip()

    # Rationale bullets for the report: prefer the concrete risks, back-fill with
    # generic signals, and surface any documentation gaps the model flagged.
    rationale = _as_list(data.get("major_accessibility_risks"))
    rationale += _as_list(data.get("rationale") or data.get("reasons"))
    if not rationale:
        rationale = _as_list(data.get("signals_found"))
    for gap in _as_list(data.get("missing_or_unclear_information")):
        rationale.append(f"Missing/unclear: {gap}")

    # Recommendations: the single-line recommendation first, then the steps.
    recommendations = []
    rec = str(data.get("recommendation") or "").strip()
    if rec:
        recommendations.append(rec)
    recommendations += _as_list(data.get("next_steps") or data.get("recommendations"))

    return AIReview(
        verdict=_match_verdict(data.get("category") or data.get("verdict")),
        impact_level=_match_impact(
            data.get("risk_level") or data.get("impact_level") or data.get("impact")
        ),
        rationale=rationale,
        summary=summary,
        recommendations=recommendations,
        raw_text=raw,
        parsed_ok=True,
    )


def review_with_ai(result: ReviewResult, settings: dict[str, Any] | None = None) -> AIReview:
    """Run the full AI review for a parsed VPAT. Raises on Bedrock transport error."""
    cfg = BedrockConfig.from_settings(settings)
    prompt = build_prompt(result)
    raw = invoke(prompt, cfg)
    return parse_ai_reply(raw)
