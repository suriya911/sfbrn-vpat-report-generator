"""The five review verdicts, and the deterministic way to reach one.

One vocabulary, three consumers: the rubric asks a model for exactly these
strings (``ai/data/risk_review_prompt.md``), the validator accepts only these
(``ai/response.py``), and the GUI files a report into a folder per these. They
live here because they are the domain's vocabulary — a verdict is what this app
is *for*. The AI happens to be one way to reach one; ``classify_report`` is the
other, and it is the one that runs whenever Bedrock is unavailable.

Keeping this out of ``ui/gui/`` matters beyond tidiness: ``classify_report`` is
pure, it is the fallback on every offline run, and it needs tests. While it lived
in the Tkinter module, testing it (or generating the samples) meant importing Tk.
"""

from __future__ import annotations

#: The five verdicts, in descending order of confidence in the product.
#: A model may answer with these and nothing else.
CATEGORIES: tuple[str, ...] = (
    "Good to Go",
    "Minor Issue",
    "Needs Manual Review",
    "Need TAAP",
    "Deny",
)


def classify_report(
    score: int | None,
    impact_level: str,
    barriers: int,
    access: str,
    good_cut: int = 90,
) -> str:
    """Map a finished review to one of the five verdicts.

    The deterministic heuristic: what the app concludes with no model involved.
    It runs when the AI review is switched off, and whenever a model call fails
    or answers with something we cannot read as a verdict.

    ``score`` is 0-100, or ``None`` when it could not be computed — which is not
    a low score but an absent one, and so resolves to a human, not a judgment.
    ``impact_level`` is Low/Medium/High.
    """
    if score is None:
        return "Needs Manual Review"
    if access == "denies_access" and impact_level == "High":
        return "Deny"
    if impact_level == "High" and score < 50:
        return "Deny"
    if impact_level == "High":
        return "Need TAAP"
    if score >= good_cut and barriers == 0:
        return "Good to Go"
    if score >= 70:
        return "Minor Issue"
    return "Needs Manual Review"
