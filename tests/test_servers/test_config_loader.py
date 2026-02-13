"""Tests for config_loader module."""

from pathlib import Path

import pytest

from .config_loader import ConfigParseError, load_test_server_config


class TestLoadTestServerConfig:
    """Tests for load_test_server_config function."""

    def test_valid_yaml_config(self, tmp_path: Path) -> None:
        """Test loading a valid YAML config file."""
        config_file = tmp_path / "test_servers.yaml"
        config_file.write_text("""
test-servers:
  radicale:
    type: embedded
    enabled: true
""")
        cfg = load_test_server_config(str(config_file))
        assert "radicale" in cfg
        assert cfg["radicale"]["type"] == "embedded"

    def test_valid_json_config(self, tmp_path: Path) -> None:
        """Test loading a valid JSON config file."""
        config_file = tmp_path / "test_servers.json"
        config_file.write_text('{"test-servers": {"radicale": {"type": "embedded"}}}')
        cfg = load_test_server_config(str(config_file))
        assert "radicale" in cfg
        assert cfg["radicale"]["type"] == "embedded"

    def test_invalid_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid YAML raises ConfigParseError."""
        config_file = tmp_path / "test_servers.yaml"
        config_file.write_text("""
test-servers:
  radicale:
    type: embedded
    invalid yaml: [unclosed bracket
""")
        with pytest.raises(ConfigParseError) as exc_info:
            load_test_server_config(str(config_file))
        assert "could not be parsed" in str(exc_info.value)
        assert str(config_file) in str(exc_info.value)

    def test_invalid_json_and_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test that content invalid as both JSON and YAML raises ConfigParseError."""
        config_file = tmp_path / "test_servers.json"
        # This is invalid for both JSON and YAML parsers
        config_file.write_text("{{{{invalid syntax}}}}")
        with pytest.raises(ConfigParseError) as exc_info:
            load_test_server_config(str(config_file))
        assert "could not be parsed" in str(exc_info.value)

    def test_nonexistent_explicit_config_falls_back(self, tmp_path: Path, monkeypatch) -> None:
        """Test that nonexistent explicit config falls back to default locations."""
        # Temporarily change to a directory without any config files
        # and set HOME to temp dir to avoid finding real user configs
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        cfg = load_test_server_config("/nonexistent/path/test_servers.yaml")
        # Should return empty dict when no config found in any location
        assert cfg == {}

    def test_flat_yaml_config(self, tmp_path: Path) -> None:
        """Test loading a YAML config without test-servers wrapper."""
        config_file = tmp_path / "test_servers.yaml"
        config_file.write_text("""
radicale:
    type: embedded
    enabled: true
purelymail:
    type: external
    enabled: true
    features: purelymail
""")
        cfg = load_test_server_config(str(config_file))
        assert "radicale" in cfg
        assert "purelymail" in cfg
        assert cfg["purelymail"]["features"] == "purelymail"

    def test_empty_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test that an empty YAML file raises ConfigParseError."""
        config_file = tmp_path / "test_servers.yaml"
        config_file.write_text("")
        with pytest.raises(ConfigParseError) as exc_info:
            load_test_server_config(str(config_file))
        assert "could not be parsed" in str(exc_info.value)
