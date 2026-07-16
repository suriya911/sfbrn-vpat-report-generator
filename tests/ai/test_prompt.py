"""The rubric loads from the package, and the record goes into it intact.

The substitution looks trivial and is not: the rubric embeds its own output
schema as literal JSON, so the obvious ``str.format`` would raise on the schema's
braces, and any escaping that fixed that would make the rubric unreadable to the
person editing it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vpat_reviewer.ai import prompt
from vpat_reviewer.ai.base import AssessmentError


def _record() -> dict:
    return {
        "document_kind": "vpat",
        "product_name": "Acme Learn",
        "score": 33,
        "criteria": [
            {"id": "1.4.3", "raw_status": "Partially Supports", "status": "Partially Supports"}
        ],
    }


def test_rubric_is_packaged_and_loads():
    """The prompt must ship inside the package, not beside it.

    It used to be a loose ``prompt.txt`` located by walking up from ``__file__``,
    which resolves to nothing inside a PyInstaller bundle -- so the shipped exe
    raised FileNotFoundError, the GUI swallowed it, and the AI silently never ran.
    """
    text = prompt.template()
    assert prompt.PLACEHOLDER in text
    assert "accessibility compliance reviewer" in text


def test_rubric_states_every_category():
    """The rubric and the validator must not drift apart.

    They are two halves of one contract: the rubric asks for these strings and
    ``response.parse`` accepts only these strings. A rename in one alone means
    every reply is rejected and no verdict is ever recorded.
    """
    from vpat_reviewer.ai.base import CATEGORIES

    text = prompt.template()
    for category in CATEGORIES:
        assert category in text


def test_rubric_is_bundled_by_the_pyinstaller_spec():
    """Packaged data PyInstaller isn't told about is packaged data the exe lacks.

    Checking the spec as text is crude, but the alternative is that a `datas`
    regression is invisible until someone ships a build with no AI in it.
    """
    spec = (Path(__file__).parents[2] / "vpat_reviewer.spec").read_text(encoding="utf-8")
    assert "ai/data/risk_review_prompt.md" in spec


def test_render_substitutes_the_record_as_json():
    rendered = prompt.render(_record())
    assert prompt.PLACEHOLDER not in rendered
    assert '"product_name": "Acme Learn"' in rendered
    assert "Acme Learn" in rendered


def test_render_keeps_the_output_schema_braces_verbatim():
    """The str.format regression: the schema's braces are content, not fields.

    ``str.format`` would read ``{"category": ...}`` as a field reference and
    raise KeyError. If this ever fails, someone reached for format().
    """
    rendered = prompt.render(_record())
    assert '"category": "Good to Go | Minor Issue' in rendered
    assert '"needs_human_review": true' in rendered
    assert '"ada_relevance": ""' in rendered


def test_render_survives_braces_in_vendor_text():
    """Vendor remarks are arbitrary text and routinely contain braces."""
    record = {"criteria": [{"id": "1.1.1", "remarks": "Uses {handlebars} and {{doubled}} syntax"}]}
    rendered = prompt.render(record)
    assert "{handlebars}" in rendered


def test_render_produces_a_prompt_ending_in_parseable_json():
    """What we send must actually be the record, not a repr of it."""
    rendered = prompt.render(_record())
    payload = rendered.split("VPAT/ACR content:\n", 1)[1]
    assert json.loads(payload)["product_name"] == "Acme Learn"


def test_render_rejects_a_template_with_no_placeholder(monkeypatch: pytest.MonkeyPatch):
    """A rubric with nowhere to put the document would still get a verdict back.

    The model would answer from the rubric alone. Failing loudly is the whole
    point -- a confident verdict drawn from no evidence is the worst output this
    project can produce.
    """
    monkeypatch.setattr(prompt, "template", lambda: "Classify the document.")
    with pytest.raises(AssessmentError, match="placeholder"):
        prompt.render(_record())
