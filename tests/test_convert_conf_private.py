"""The conf_private.py converter must not clobber an existing YAML file."""

import sys
from pathlib import Path

import pytest
import yaml

from tests.tools import convert_conf_private

CONF_PRIVATE = """\
caldav_servers = [
    {"name": "example", "url": "https://caldav.example.com/", "username": "u", "password": "p"},
]
"""


def converted_url(text: str) -> str:
    """The example server's URL in the generated YAML."""
    return yaml.safe_load(text)["test-servers"]["example"]["url"]


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["convert_conf_private.py", *args])
    convert_conf_private.main()


def test_refuses_to_overwrite_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conf = tmp_path / "conf_private.py"
    conf.write_text(CONF_PRIVATE)
    out = tmp_path / "caldav_test_servers.yaml"
    out.write_text("precious: true\n")

    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, str(conf), str(out))

    assert exc.value.code != 0
    assert out.read_text() == "precious: true\n"


def test_force_overwrites_existing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "conf_private.py"
    conf.write_text(CONF_PRIVATE)
    out = tmp_path / "caldav_test_servers.yaml"
    out.write_text("precious: true\n")

    run(monkeypatch, "--force", str(conf), str(out))

    assert converted_url(out.read_text()) == "https://caldav.example.com/"


def test_writes_new_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    conf = tmp_path / "conf_private.py"
    conf.write_text(CONF_PRIVATE)
    out = tmp_path / "caldav_test_servers.yaml"

    run(monkeypatch, str(conf), str(out))

    assert converted_url(out.read_text()) == "https://caldav.example.com/"


def test_dry_run_leaves_existing_output_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    conf = tmp_path / "conf_private.py"
    conf.write_text(CONF_PRIVATE)
    out = tmp_path / "caldav_test_servers.yaml"
    out.write_text("precious: true\n")

    run(monkeypatch, "--dry-run", str(conf), str(out))

    assert out.read_text() == "precious: true\n"
    out_text = capsys.readouterr().out
    _, marker, printed = out_text.partition("--- Generated YAML ---\n")
    assert marker, out_text
    assert converted_url(printed) == "https://caldav.example.com/"
