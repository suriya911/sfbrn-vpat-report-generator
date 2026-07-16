"""The Bedrock adapter's configuration — everything short of the call itself.

No network and no mocks: what is worth pinning here is where the model id comes
from and, above all, where the credential does *not* come from.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vpat_reviewer.ai.base import RiskAssessor
from vpat_reviewer.ai.bedrock import (
    BEARER_ENV,
    DEFAULT_MODEL_ID,
    BedrockAssessor,
    BedrockConfig,
    _bearer_token,
)

_BEDROCK_ENV = (
    BEARER_ENV,
    "VPAT_BEDROCK_API_KEY",
    "VPAT_BEDROCK_API_KEY_FILE",
    "VPAT_BEDROCK_REGION",
    "VPAT_BEDROCK_MODEL_ID",
    "VPAT_BEDROCK_PROFILE",
)


def _clear_bedrock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the developer's own AWS setup.

    Without this a machine with real credentials exported gets different results
    than CI, and the credential tests below would pass for the wrong reason.
    """
    for name in _BEDROCK_ENV:
        monkeypatch.delenv(name, raising=False)
    # _default_key_file() looks next to settings.json; point that somewhere empty.
    monkeypatch.setenv("VPAT_SETTINGS_PATH", str(Path(__file__).parent / "no_such_settings.json"))


def test_bedrock_assessor_satisfies_the_port():
    assert isinstance(BedrockAssessor(BedrockConfig()), RiskAssessor)


def test_the_assessor_reports_the_model_it_would_ask(monkeypatch: pytest.MonkeyPatch):
    _clear_bedrock_env(monkeypatch)
    assert BedrockAssessor(BedrockConfig(model_id="some.model.v1")).model_id == "some.model.v1"


def test_a_key_in_settings_is_ignored(monkeypatch: pytest.MonkeyPatch):
    """settings.json is tracked in git, so a token in it is a published token.

    There is deliberately no code path that reads one -- that is what makes the
    rule enforceable rather than merely documented.
    """
    _clear_bedrock_env(monkeypatch)
    cfg = BedrockConfig.from_settings(
        {"bedrock_api_key": "leaked-token", "bedrock_api_key_file": "/tmp/leak.txt"}
    )
    assert cfg.api_key == ""


def test_the_key_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    _clear_bedrock_env(monkeypatch)
    monkeypatch.setenv(BEARER_ENV, "  token-from-env  ")
    assert BedrockConfig.from_settings({}).api_key == "token-from-env"


def test_the_key_comes_from_a_drop_in_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The gitignored key file is the sanctioned way to share one across a team."""
    _clear_bedrock_env(monkeypatch)
    key_file = tmp_path / "bedrock_api_key.txt"
    key_file.write_text("token-from-file\n", encoding="utf-8")
    monkeypatch.setenv("VPAT_BEDROCK_API_KEY_FILE", str(key_file))
    assert BedrockConfig.from_settings({}).api_key == "token-from-file"


def test_env_wins_over_settings_for_the_model(monkeypatch: pytest.MonkeyPatch):
    """One build, many machines: an env var retargets it without a code change."""
    _clear_bedrock_env(monkeypatch)
    monkeypatch.setenv("VPAT_BEDROCK_MODEL_ID", "env.model.v1")
    cfg = BedrockConfig.from_settings({"bedrock_model_id": "settings.model.v1"})
    assert cfg.model_id == "env.model.v1"


def test_settings_are_used_when_the_environment_is_silent(monkeypatch: pytest.MonkeyPatch):
    _clear_bedrock_env(monkeypatch)
    cfg = BedrockConfig.from_settings(
        {"bedrock_model_id": "settings.model.v1", "bedrock_region": "eu-west-1"}
    )
    assert cfg.model_id == "settings.model.v1"
    assert cfg.region == "eu-west-1"


def test_defaults_apply_with_no_settings_at_all(monkeypatch: pytest.MonkeyPatch):
    _clear_bedrock_env(monkeypatch)
    cfg = BedrockConfig.from_settings(None)
    assert cfg.model_id == DEFAULT_MODEL_ID
    assert cfg.region == "us-west-2"


def test_the_tuning_knobs_are_actually_read(monkeypatch: pytest.MonkeyPatch):
    """Both were dead: max_tokens had no default to read, temperature no read at all."""
    _clear_bedrock_env(monkeypatch)
    cfg = BedrockConfig.from_settings({"bedrock_max_tokens": 8192, "bedrock_temperature": 0.7})
    assert cfg.max_tokens == 8192
    assert cfg.temperature == 0.7


def test_nonsense_knobs_fall_back_rather_than_crash(monkeypatch: pytest.MonkeyPatch):
    _clear_bedrock_env(monkeypatch)
    cfg = BedrockConfig.from_settings({"bedrock_max_tokens": "lots"})
    assert cfg.max_tokens == 4096


def test_the_bearer_token_is_put_back(monkeypatch: pytest.MonkeyPatch):
    """Supplying the token means setting a process-wide variable.

    Leaving it set would silently change how every later call in the process
    authenticates -- including ones that meant to use a profile.
    """
    _clear_bedrock_env(monkeypatch)
    monkeypatch.setenv(BEARER_ENV, "original")
    with _bearer_token("temporary"):
        assert os.environ[BEARER_ENV] == "temporary"
    assert os.environ[BEARER_ENV] == "original"


def test_the_bearer_token_is_removed_when_there_was_none(monkeypatch: pytest.MonkeyPatch):
    _clear_bedrock_env(monkeypatch)
    with _bearer_token("temporary"):
        assert os.environ[BEARER_ENV] == "temporary"
    assert BEARER_ENV not in os.environ
