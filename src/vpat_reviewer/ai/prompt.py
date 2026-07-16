"""The review rubric, and putting a review record into it.

The rubric itself lives in ``assessment/data/risk_review_prompt.md`` — the
classification categories, the decision rules, and the output schema the model
must answer with. Editing that Markdown (not code) changes what we ask. This
module just loads it and substitutes the record.

It is packaged data rather than a doc for the same reason ``wcag.json`` is: the
frozen exe has no ``docs/`` directory, so a prompt read from there would work in
development and vanish in the shipped app.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from vpat_reviewer.ai.base import AssessmentError

#: The one substitution point in the rubric.
PLACEHOLDER = "{{vpat_acr_content}}"


@lru_cache(maxsize=1)
def template() -> str:
    """The rubric as written, placeholder unsubstituted (cached)."""
    resource = files("vpat_reviewer.ai") / "data" / "risk_review_prompt.md"
    return resource.read_text(encoding="utf-8")


def render(record: dict[str, Any]) -> str:
    """Substitute a review record into the rubric and return the full prompt.

    Substitution is a literal ``str.replace``, never ``str.format``: the rubric
    embeds the expected output as literal JSON, so every ``{`` and ``}`` in it is
    content. ``format`` would read ``{"category": ...}`` as a field reference and
    raise; escaping them would mean the rubric on disk no longer reads as the
    JSON we are asking the model to produce, which makes it harder to edit
    correctly — the one thing this file exists to keep easy.
    """
    text = template()
    if PLACEHOLDER not in text:
        # Without this the model would get the rubric and no document, and would
        # have nothing to classify but its own expectations. It would still
        # answer. A missing placeholder must fail loudly, not silently invite a
        # verdict drawn from nothing.
        raise AssessmentError(f"The rubric has no {PLACEHOLDER} placeholder to substitute into.")
    payload = json.dumps(record, indent=2, ensure_ascii=False)
    return text.replace(PLACEHOLDER, payload)
