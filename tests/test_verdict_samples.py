"""The five sample VPATs still reach the verdicts they were built to reach.

``samples/verdict_cases/`` holds one synthetic document per verdict, each with
the parse it should produce. Until now nothing asserted them: the generator
checked its own work at generation time and the committed files were read by
nobody.

They are worth asserting because they cover ``classify_report``, which is the
deterministic fallback — what the app concludes whenever Bedrock is switched
off, unreachable, or answers with something we cannot read. It runs on every
offline report and had no tests at all.

No model is involved here. This is the offline half of the pipeline only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.policy import GradingPolicy
from vpat_reviewer.domain.scoring import get_barriers
from vpat_reviewer.domain.verdict import CATEGORIES, classify_report
from vpat_reviewer.service import analyze

CASES = sorted((Path(__file__).parents[1] / "samples" / "verdict_cases").glob("*.expected.json"))


def _sample(expected_path: Path) -> tuple[dict, Path]:
    return json.loads(expected_path.read_text(encoding="utf-8")), expected_path.with_suffix("")


def test_the_samples_are_present():
    """A silently empty parametrize would make every test below vacuous."""
    assert len(CASES) == 5


@pytest.mark.parametrize("expected_path", CASES, ids=lambda p: p.name.split(".")[0])
def test_sample_reaches_its_expected_verdict(expected_path: Path):
    expected, stem = _sample(expected_path)
    doc = stem.with_suffix(".txt")

    result = analyze(str(doc), policy=GradingPolicy.default())
    barriers = get_barriers(result.document, GradingPolicy.default())
    answers = expected["recommended_answers"]
    impact = calculate_impact(answers, barriers, result.score, GradingPolicy.default())

    verdict = classify_report(
        result.score["score"],
        impact["suggested_level"],
        len(barriers),
        answers["access_impact"],
    )
    assert verdict == expected["expected_verdict"]
    assert verdict in CATEGORIES


@pytest.mark.parametrize("expected_path", CASES, ids=lambda p: p.name.split(".")[0])
def test_sample_still_parses_to_its_recorded_score(expected_path: Path):
    """The samples double as parser goldens — a drifting score would hide a drifting verdict."""
    expected, stem = _sample(expected_path)
    result = analyze(str(stem.with_suffix(".txt")), policy=GradingPolicy.default())
    assert result.score["score"] == expected["score"]
    assert result.document.product_name == expected["product_name"]
