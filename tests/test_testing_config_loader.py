"""Tests for config_loader module."""

from pathlib import Path

import pytest

from caldav.testing.config_loader import ConfigParseError, load_test_server_config


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
        from caldav.testing import config_loader

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(config_loader, "TEST_CONFIG_LOCATIONS", [])
        monkeypatch.setattr(config_loader, "get_all_test_servers", dict)
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

    def test_rfc6638_users_preserved_alongside_test_servers(self, tmp_path: Path) -> None:
        """rfc6638_users at top level is preserved when test-servers is unwrapped."""
        config_file = tmp_path / "test_servers.yaml"
        config_file.write_text("""
test-servers:
  radicale:
    type: embedded
    enabled: true

rfc6638_users:
  - url: http://localhost:8802/dav/calendars/user/user1
    username: user1
    password: x
  - url: http://localhost:8802/dav/calendars/user/user2
    username: user2
    password: x
""")
        cfg = load_test_server_config(str(config_file))
        assert "radicale" in cfg
        assert "rfc6638_users" in cfg
        assert len(cfg["rfc6638_users"]) == 2
        assert cfg["rfc6638_users"][0]["username"] == "user1"

    def test_rfc6638_users_only_config(self, tmp_path: Path) -> None:
        """Config with only rfc6638_users (no test-servers) works correctly."""
        config_file = tmp_path / "test_servers.yaml"
        config_file.write_text("""
rfc6638_users:
  - url: http://localhost:8802/dav/calendars/user/user1
    username: user1
    password: x
""")
        cfg = load_test_server_config(str(config_file))
        assert "rfc6638_users" in cfg
        assert cfg["rfc6638_users"][0]["url"] == "http://localhost:8802/dav/calendars/user/user1"


class TestEnabledFalseDisablesRegisteredServer:
    """Gate finding F16: `enabled: false` was a no-op for docker servers.

    ``auto_discover()`` registers every ``docker-test-servers/*`` directory
    before ``load_from_config()`` runs, and the ``enabled`` check only skipped
    the *config entry* -- the already-registered server stayed enabled.  So a
    user who copied the example file and had Docker got every server run
    anyway, the opposite of what the file says.
    """

    def _registry_with_registered_server(self):
        from caldav.testing.base import TestServer
        from caldav.testing.registry import ServerRegistry

        class _FakeDocker(TestServer):
            server_type = "docker"

            def start(self) -> None: ...

            def stop(self) -> None: ...

            def is_running(self) -> bool:
                return True

            def is_accessible(self) -> bool:
                return True

            @property
            def url(self) -> str:
                return "http://localhost:8800/"

        registry = ServerRegistry()
        registry.register(_FakeDocker({"name": "baikal", "host": "localhost", "port": 8800}))
        return registry

    def test_enabled_false_disables_an_autodiscovered_server(self, monkeypatch) -> None:
        monkeypatch.delenv("PYTHON_CALDAV_TEST_DOCKER", raising=False)
        registry = self._registry_with_registered_server()
        assert [s.name for s in registry.enabled_servers()] == ["baikal"]

        registry.load_from_config({"baikal": {"type": "docker", "enabled": False}})

        assert registry.enabled_servers() == []

    def test_enabled_true_leaves_it_alone(self, monkeypatch) -> None:
        monkeypatch.delenv("PYTHON_CALDAV_TEST_DOCKER", raising=False)
        registry = self._registry_with_registered_server()

        registry.load_from_config({"baikal": {"type": "docker", "enabled": True}})

        assert [s.name for s in registry.enabled_servers()] == ["baikal"]


class TestConfigSourcesUnion:
    """https://github.com/python-caldav/caldav/issues/817: every source counts.

    The loader used to stop at the first source it found, so a test-server
    yaml hid the ``test_allowed`` sections of the caldav configuration.
    """

    @pytest.fixture
    def sources(self, tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
        from caldav.testing import config_loader

        checkout_yaml = tmp_path / "checkout.yaml"
        user_yaml = tmp_path / "user.yaml"
        monkeypatch.setattr(
            config_loader, "TEST_CONFIG_LOCATIONS", [str(checkout_yaml), str(user_yaml)]
        )
        monkeypatch.setattr(
            config_loader,
            "get_all_test_servers",
            lambda: {
                "fromconf": {"url": "https://conf.example.com/"},
                "both": {"url": "https://conf-both.example.com/"},
            },
        )
        return checkout_yaml, user_yaml

    def test_union_of_yaml_files_and_test_allowed(self, sources) -> None:
        checkout_yaml, user_yaml = sources
        checkout_yaml.write_text(
            "test-servers:\n"
            "  fromcheckout: {type: external, url: 'https://checkout.example.com/'}\n"
            "  both: {type: external, url: 'https://yaml-both.example.com/'}\n"
        )
        user_yaml.write_text(
            "fromuser: {type: external, url: 'https://user.example.com/'}\n"
            "fromcheckout: {type: external, url: 'https://shadowed.example.com/'}\n"
        )
        cfg = load_test_server_config()
        assert set(cfg) == {"fromcheckout", "fromuser", "fromconf", "both"}
        ## Earlier sources win on a name clash
        assert cfg["fromcheckout"]["url"] == "https://checkout.example.com/"
        assert cfg["both"]["url"] == "https://yaml-both.example.com/"
        assert cfg["fromconf"]["type"] == "external"
        assert cfg["fromconf"]["enabled"] is True

    def test_name_clash_is_case_insensitive(self, sources) -> None:
        checkout_yaml, _ = sources
        checkout_yaml.write_text("Both: {type: external, enabled: false}\n")
        cfg = load_test_server_config()
        assert "both" not in cfg
        assert cfg["Both"]["enabled"] is False

    def test_broken_caldav_config_keeps_yaml_servers(self, sources, monkeypatch) -> None:
        from caldav.testing import config_loader

        checkout_yaml, _ = sources
        checkout_yaml.write_text("fromcheckout: {type: external, url: 'https://c.example.com/'}\n")

        def broken():
            raise ValueError("not a mapping of sections")

        monkeypatch.setattr(config_loader, "get_all_test_servers", broken)
        with pytest.warns(UserWarning, match="test_allowed"):
            cfg = load_test_server_config()
        assert set(cfg) == {"fromcheckout"}

    def test_explicit_file_is_used_alone(self, sources, tmp_path: Path) -> None:
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text("only: {type: external, url: 'https://only.example.com/'}\n")
        assert set(load_test_server_config(str(explicit))) == {"only"}

    def test_checkout_yaml_does_not_depend_on_cwd(self, tmp_path: Path, monkeypatch) -> None:
        from caldav.testing import config_loader

        monkeypatch.chdir(tmp_path)
        # The directory is resolved, not the file: a developer's yaml may be a symlink
        checkout_yaml = Path(__file__).resolve().parent / "caldav_test_servers.yaml"
        assert checkout_yaml in [
            Path(loc).expanduser().parent.resolve() / Path(loc).name
            for loc in config_loader.TEST_CONFIG_LOCATIONS
        ]


class TestExternalServerAccessibility:
    """https://github.com/python-caldav/caldav/issues/817: probe external servers."""

    @pytest.fixture
    def listener(self):
        import socket

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        yield sock.getsockname()[1]
        sock.close()

    def test_reachable(self, listener: int) -> None:
        from caldav.testing.base import ExternalTestServer

        server = ExternalTestServer({"name": "ext", "url": f"http://127.0.0.1:{listener}/dav/"})
        assert server.is_accessible()

    def test_unreachable(self) -> None:
        import socket

        from caldav.testing.base import ExternalTestServer

        ## Grab a free port, then release it, so nothing listens there
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        server = ExternalTestServer({"name": "ext", "url": f"http://127.0.0.1:{port}/"})
        assert not server.is_accessible()

    def test_bare_domain_without_features(self) -> None:
        from caldav.testing.base import ExternalTestServer

        server = ExternalTestServer({"name": "ext", "url": "dav.invalid"})
        assert not server.is_accessible()

    def test_url_from_features(self, listener: int) -> None:
        from caldav.testing.base import ExternalTestServer

        server = ExternalTestServer(
            {
                "name": "ext",
                "features": {
                    "auto-connect.url": {
                        "domain": f"127.0.0.1:{listener}",
                        "scheme": "http",
                        "basepath": "/",
                    }
                },
            }
        )
        assert server.is_accessible()
