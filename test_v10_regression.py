"""
VPAT Reviewer v10 - regression suite.

RECONSTRUCTED FILE. The original test_v10_regression.py was lost in the
file-name shuffle (its slot on disk had been overwritten with the
report_generator source). This suite is rebuilt from the invariants documented
in BUILD_INSTRUCTIONS.md so the safety net described there still exists:

    - Not-Applicable excluded from the scoring denominator (Option A policy)
    - status-normalization order ("Partial Support" must NOT become "Supports")
    - get_aa_barriers excludes Supports and Not Applicable
    - impact scale de-duplication (audience + deployment combined as max, not sum)
    - end-to-end report generation + post-generation validation

The CCPS 57% / Minitab 91% document anchors cannot be reproduced here because
the original vendor fixture files are not part of the source tree; run those
two documents through the app manually per the BUILD_INSTRUCTIONS release
checklist. Every rule those anchors exercised (NA exclusion, normalization) is
covered below with synthetic fixtures.

Run with:   python -m pytest test_v10_regression.py -q
        or: python test_v10_regression.py      (no pytest required)
"""

import os
import tempfile

from vpat_reviewer.domain.impact import calculate_impact
from vpat_reviewer.domain.models import VPATCriterion, VPATData
from vpat_reviewer.domain.normalization import normalize_status
from vpat_reviewer.domain.scoring import compliance_score, get_barriers as get_aa_barriers
from vpat_reviewer.reporting.reportlab_renderer import generate_report, validate_report


# ── fixtures ──────────────────────────────────────────────────────────────────

def _crit(cid, level, status, remarks="", section="wcag"):
    return VPATCriterion(
        criterion_id=cid, level=level, raw_status=status,
        normalized_status=normalize_status(status), remarks=remarks, section=section,
    )


def _sample_data():
    """3 AA supported, 1 AA partial, 1 AA not-applicable, 1 AA not-evaluated."""
    d = VPATData(product_name="TestProduct", vendor_name="TestVendor")
    d.criteria = [
        _crit("1.4.3", "AA", "Supports"),
        _crit("1.4.4", "AA", "Supports"),
        _crit("2.4.6", "AA", "Supports"),
        _crit("3.3.3", "AA", "Partially Supports", "Some gaps."),
        _crit("1.2.4", "AA", "Not Applicable", "No live media."),
        _crit("4.1.3", "AA", "Not Evaluated"),
        _crit("2.1.1", "A", "Supports"),
    ]
    return d


# ── 1. status normalization order ─────────────────────────────────────────────

def test_normalization_partial_is_not_supports():
    # "Partial Support" (no trailing s) must never collapse to "Supports"
    assert normalize_status("Partial Support") == "Partially Supports"
    assert normalize_status("partially supports") == "Partially Supports"
    assert normalize_status("Supports with Exceptions") == "Partially Supports"
    assert normalize_status("Supports") == "Supports"
    assert normalize_status("Does Not Support") == "Does Not Support"
    assert normalize_status("N/A") == "Not Applicable"
    assert normalize_status("") == "Not Evaluated"


# ── 2. Not-Applicable excluded from the denominator (Option A scoring) ─────────

def test_na_excluded_from_denominator():
    info = compliance_score(_sample_data())
    # 5 AA reviewable (NA excluded), 3 supported -> 60
    assert info["na_excluded"] == 1
    assert info["total"] == 5
    assert info["supported"] == 3
    assert info["score"] == 60


def test_score_all_supported_is_100():
    d = VPATData()
    d.criteria = [_crit(c, "AA", "Supports") for c in ("1.4.3", "1.4.4", "2.4.6")]
    assert compliance_score(d)["score"] == 100


def test_score_none_when_no_reviewable_aa():
    d = VPATData()
    d.criteria = [_crit("1.2.4", "AA", "Not Applicable"), _crit("2.1.1", "A", "Supports")]
    assert compliance_score(d)["score"] is None


# ── 3. barrier selection ──────────────────────────────────────────────────────

def test_get_aa_barriers_excludes_supports_and_na():
    barriers = get_aa_barriers(_sample_data())
    ids = {b.criterion_id for b in barriers}
    # Partial + Not-Evaluated are barriers; Supports and Not-Applicable are not.
    assert ids == {"3.3.3", "4.1.3"}


# ── 4. impact scale de-duplication (audience + deployment combined) ────────────

def test_impact_scale_not_double_counted():
    d = _sample_data()
    score_info = compliance_score(d)
    barriers = get_aa_barriers(d)
    # campus_wide on BOTH axes must not stack into High on scale alone.
    answers = {"audience": "campus_wide", "access_impact": "no_limit",
               "legal_exposure": "low", "deployment": "campus_wide"}
    result = calculate_impact(answers, barriers, score_info)
    assert result["suggested_level"] in ("Low", "Medium")
    assert result["suggested_level"] != "High"


def test_impact_high_when_access_denied():
    d = _sample_data()
    answers = {"audience": "campus_wide", "access_impact": "denies_access",
               "legal_exposure": "high", "deployment": "campus_wide"}
    result = calculate_impact(answers, get_aa_barriers(d), compliance_score(d))
    assert result["suggested_level"] == "High"


# ── 5. end-to-end report generation + validation ──────────────────────────────

def test_generate_and_validate_report():
    d = _sample_data()
    score_info = compliance_score(d)
    answers = {"audience": "department", "access_impact": "limits_some",
               "legal_exposure": "medium", "deployment": "department"}
    impact = calculate_impact(answers, get_aa_barriers(d), score_info)
    impact["final_level"] = impact["suggested_level"]

    out = os.path.join(tempfile.gettempdir(), "vpat_regression_report.pdf")
    if os.path.exists(out):
        os.remove(out)
    generate_report(d, score_info, impact, answers, out, logo_path="")
    assert os.path.exists(out) and os.path.getsize(out) > 0

    ok, problems = validate_report(out)
    assert ok, f"validation failed: {problems}"


# ── no-pytest fallback runner ─────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.disable(logging.CRITICAL)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    raise SystemExit(0 if passed == len(tests) else 1)
