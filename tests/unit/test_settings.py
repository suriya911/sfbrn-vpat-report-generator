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
