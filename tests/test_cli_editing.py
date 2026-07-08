import json

import pytest

from vpat_reviewer.cli import main


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("VPAT_SETTINGS_PATH", str(tmp_path / "settings.json"))


def test_policy_set_and_show(capsys):
    assert main(["policy", "set", "compliance_threshold", "80"]) == 0
    capsys.readouterr()
    assert main(["policy", "show"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["compliance_threshold"] == 80


def test_policy_set_invalid_returns_1():
    assert main(["policy", "set", "compliance_threshold", "abc"]) == 1


def test_policy_reset(capsys):
    main(["policy", "set", "graded_level", "A"])
    capsys.readouterr()
    assert main(["policy", "reset"]) == 0
    capsys.readouterr()
    main(["policy", "show"])
    assert json.loads(capsys.readouterr().out)["graded_level"] == "AA"


def test_policy_import(tmp_path, capsys):
    pol = tmp_path / "p.json"
    pol.write_text(json.dumps({"compliance_threshold": 70}), encoding="utf-8")
    assert main(["policy", "import", str(pol)]) == 0
    capsys.readouterr()
    main(["policy", "show"])
    assert json.loads(capsys.readouterr().out)["compliance_threshold"] == 70


def test_settings_set_and_show(capsys):
    assert main(["settings", "set", "org_name", "Acme University"]) == 0
    capsys.readouterr()
    main(["settings", "show"])
    assert json.loads(capsys.readouterr().out)["org_name"] == "Acme University"


def test_settings_set_unknown_key_returns_1():
    assert main(["settings", "set", "bogus", "x"]) == 1


def test_editing_policy_and_settings_do_not_clobber_each_other(capsys):
    main(["policy", "set", "compliance_threshold", "77"])
    main(["settings", "set", "org_name", "Kept University"])
    capsys.readouterr()
    main(["policy", "show"])
    assert json.loads(capsys.readouterr().out)["compliance_threshold"] == 77
    main(["settings", "show"])
    assert json.loads(capsys.readouterr().out)["org_name"] == "Kept University"
