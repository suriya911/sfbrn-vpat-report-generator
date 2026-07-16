from pathlib import Path

from vpat_reviewer.config import settings
from vpat_reviewer.domain.policy import GradingPolicy


def test_defaults_and_first_run(tmp_path: Path):
    p = tmp_path / "settings.json"
    assert settings.is_first_run(p)
    assert settings.load_settings(p)["org_short"] == "SFBRN"
    assert settings.load_policy(p) == GradingPolicy.default()


def test_threshold_is_coerced(tmp_path: Path):
    p = tmp_path / "settings.json"
    settings.save_settings({"threshold": "150"}, path=p)
    assert settings.load_settings(p)["threshold"] == 100  # clamped


def test_policy_preserved_when_saving_identity(tmp_path: Path):
    p = tmp_path / "settings.json"
    settings.save_policy(GradingPolicy.default().with_changes(compliance_threshold=77), path=p)
    settings.save_settings({"org_name": "ACME University"}, path=p)
    assert settings.load_policy(p).compliance_threshold == 77
    assert settings.load_settings(p)["org_name"] == "ACME University"


def test_identity_preserved_when_saving_policy(tmp_path: Path):
    p = tmp_path / "settings.json"
    settings.save_settings({"reviewer_name": "Jane Roe"}, path=p)
    settings.save_policy(GradingPolicy.default().with_changes(graded_level="A"), path=p)
    assert settings.load_settings(p)["reviewer_name"] == "Jane Roe"
    assert settings.load_policy(p).graded_level == "A"


def test_corrupt_file_falls_back(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert settings.load_settings(p)["org_short"] == "SFBRN"
    assert settings.load_policy(p) == GradingPolicy.default()


def test_ai_is_on_by_default_with_a_real_model():
    """The shipped app asks Bedrock for the verdict without being configured."""
    d = settings.IDENTITY_DEFAULTS
    assert d["use_ai"] is True
    assert d["bedrock_model_id"]
    assert d["bedrock_region"] == "us-west-2"


def test_settings_hold_no_credential():
    """settings.json is tracked in git and ships beside the exe.

    Anything stored in it is published, so no field may exist that a secret could
    plausibly go in. This is the rule as a test rather than as a comment: the
    previous version invited users to paste a bearer token in here.

    ``bedrock_max_tokens`` is a length, not a secret, and is named as an explicit
    exception so that a future ``bedrock_api_token`` still trips this.
    """
    forbidden = ("key", "token", "secret", "password", "credential", "bearer")
    benign = {"bedrock_max_tokens"}
    offenders = [
        k
        for k in settings.IDENTITY_DEFAULTS
        if k not in benign and any(w in k.lower() for w in forbidden)
    ]
    assert offenders == []


def test_the_default_model_matches_the_adapter():
    """The model id is duplicated because config must not import ai.

    An inward-pointing arrow forbids the import, so a test holds the two literals
    together instead.
    """
    from vpat_reviewer.ai.bedrock import DEFAULT_MODEL_ID

    assert settings.IDENTITY_DEFAULTS["bedrock_model_id"] == DEFAULT_MODEL_ID


def test_ai_settings_survive_a_policy_save(tmp_path: Path):
    p = tmp_path / "settings.json"
    settings.save_settings({"bedrock_model_id": "some.model.v1", "use_ai": False}, path=p)
    settings.save_policy(GradingPolicy.default().with_changes(compliance_threshold=77), path=p)
    assert settings.load_settings(p)["bedrock_model_id"] == "some.model.v1"
    assert settings.load_settings(p)["use_ai"] is False
    assert settings.load_policy(p).compliance_threshold == 77
