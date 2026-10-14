"""Tests for the test server base classes."""

import subprocess
from pathlib import Path

import pytest

from . import base
from .base import DockerTestServer


@pytest.fixture(autouse=True)
def isolated_session_locks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep session locks taken by these tests out of the real tempdir."""
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    monkeypatch.setattr(base, "_session_locks", {})
    monkeypatch.setattr(base, "_session_lock_failures", {})
    yield
    for f in base._session_locks.values():
        f.close()


@pytest.fixture
def held_elsewhere(tmp_path: Path):
    """Hold a server's session lock through a separate open file, as another process would."""
    import fcntl

    files = []

    def hold(name: str) -> None:
        f = open(base._lock_path(name, ".session"), "a+")
        files.append(f)
        fcntl.flock(f, fcntl.LOCK_EX)

    yield hold
    for f in files:
        f.close()


class UnreachableDockerServer(DockerTestServer):
    """A docker server whose start.sh fails and which never answers."""

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/dav/"

    def is_accessible(self) -> bool:
        return False


class TestDockerTestServerStart:
    def test_failed_start_is_not_retried(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed start must not re-run start.sh for every subsequent test."""
        counter = tmp_path / "runs"
        start_script = tmp_path / "start.sh"
        start_script.write_text(f"#!/bin/sh\necho run >> {counter}\nexit 1\n")
        start_script.chmod(0o755)
        monkeypatch.setattr(DockerTestServer, "verify_docker", staticmethod(lambda: True))
        server = UnreachableDockerServer({"name": "Broken", "docker_dir": str(tmp_path)})

        with pytest.raises(subprocess.CalledProcessError):
            server.start()
        with pytest.raises(RuntimeError, match="previously failed"):
            server.start()

        assert counter.read_text().count("run") == 1

    def test_parallel_starts_run_start_script_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Concurrent starts of the same server must not run start.sh twice."""
        import threading

        counter = tmp_path / "runs"
        start_script = tmp_path / "start.sh"
        start_script.write_text(f"#!/bin/sh\nsleep 1\necho run >> {counter}\n")
        start_script.chmod(0o755)
        monkeypatch.setattr(DockerTestServer, "verify_docker", staticmethod(lambda: True))
        monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

        class CountingServer(UnreachableDockerServer):
            def is_accessible(self) -> bool:
                return counter.exists()

        servers = [CountingServer({"name": "Racy", "docker_dir": str(tmp_path)}) for _ in range(3)]
        threads = [threading.Thread(target=s.start) for s in servers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.read_text().count("run") == 1
        assert sum(s._started_by_us for s in servers) == 1


class TestGetServerParams:
    def test_teardown_set_for_running_server(self, tmp_path: Path) -> None:
        """A run that restarts the container after waiting for the lock must stop it again."""

        class RunningServer(UnreachableDockerServer):
            def is_accessible(self) -> bool:
                return True

        server = RunningServer({"name": "Lambda", "docker_dir": str(tmp_path)})
        assert "teardown" in server.get_server_params()


class TestSessionLock:
    """Test runs sharing a server must not overlap; different servers may."""

    CLAIM = (
        "import sys; sys.path.insert(0, {root!r}); "
        "from tests.test_servers.base import TestServer; "
        "TestServer.claim_server({name!r})"
    )

    def _claim_in_subprocess(self, tmp_path: Path, name: str) -> subprocess.CompletedProcess:
        import os
        import sys

        root = str(Path(__file__).parents[2])
        env = dict(os.environ, TMPDIR=str(tmp_path), PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT="1")
        return subprocess.run(
            [sys.executable, "-c", self.CLAIM.format(root=root, name=name)],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_same_server_blocks_other_process(self, tmp_path: Path) -> None:
        import os

        base.TestServer.claim_server("Alpha")
        base.TestServer.claim_server("Alpha")  # re-entrant within one process
        blocked = self._claim_in_subprocess(tmp_path, "Alpha")
        assert blocked.returncode != 0
        assert f"pid {os.getpid()}" in blocked.stderr
        assert self._claim_in_subprocess(tmp_path, "Beta").returncode == 0

    def test_start_claims_server(self, tmp_path: Path) -> None:
        server = base.ExternalTestServer({"name": "Gamma", "url": "http://localhost:1/"})
        server.start()
        blocked = self._claim_in_subprocess(tmp_path, "Gamma")
        assert blocked.returncode != 0
        assert "in use" in blocked.stderr

    def test_setup_hook_set_for_running_server(self) -> None:
        """test_caldav only reaches start() (and thus the lock) via the setup hook."""
        server = base.ExternalTestServer({"name": "Delta", "url": "http://localhost:1/"})
        assert "setup" in server.get_server_params()

    def test_failed_claim_releases_lock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An error after flock() must not leave the lock held by a leaked file."""

        def fail() -> int:
            raise OSError("simulated")

        monkeypatch.setattr(base.os, "getpid", fail)
        with pytest.raises(OSError, match="simulated") as excinfo:
            base.TestServer.claim_server("Theta")
        monkeypatch.undo()
        assert "Theta" not in base._session_locks
        # excinfo keeps the failed frame, and with it any unclosed file, alive
        assert excinfo.traceback
        assert self._claim_in_subprocess(tmp_path, "Theta").returncode == 0

    def test_timeout_is_remembered(self, held_elsewhere, monkeypatch: pytest.MonkeyPatch) -> None:
        """test_caldav claims per test; a timed-out server must not wait again each time."""
        import time

        held_elsewhere("Epsilon")
        monkeypatch.setenv("PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT", "1")
        with pytest.raises(RuntimeError, match="in use"):
            base.TestServer.claim_server("Epsilon")
        t0 = time.monotonic()
        with pytest.raises(RuntimeError, match="in use"):
            base.TestServer.claim_server("Epsilon")
        assert time.monotonic() - t0 < 0.5

    def test_zero_timeout_skips_wait(self, held_elsewhere) -> None:
        """get_davclient()'s fallback must move on at once from a busy server."""
        import time

        held_elsewhere("Zeta")
        t0 = time.monotonic()
        with pytest.raises(RuntimeError, match="in use"):
            base.TestServer.claim_server("Zeta", 0)
        assert time.monotonic() - t0 < 0.5

    def test_fallback_leaves_later_claims_waiting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A busy server skipped by get_davclient() must still be waited for later."""
        import fcntl

        from caldav import config

        busy = base.ExternalTestServer({"name": "Iota", "url": "http://localhost:1/Iota/"})
        free = base.ExternalTestServer({"name": "Kappa", "url": "http://localhost:1/Kappa/"})
        monkeypatch.setattr(config, "_collect_test_servers", lambda name, config_file: [busy, free])
        with open(base._lock_path("Iota", ".session"), "a+") as other:
            fcntl.flock(other, fcntl.LOCK_EX)
            params = config._get_test_server_config(None, environment=False)
            assert params is not None and "Kappa" in params["url"]
        monkeypatch.setenv("PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT", "5")
        busy.start()

    def test_get_davclient_falls_through_busy_server(
        self, held_elsewhere, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import time

        from caldav import config

        held_elsewhere("Busy")
        monkeypatch.setenv("PYTHON_CALDAV_TEST_SERVER_LOCK_TIMEOUT", "30")
        servers = [
            base.ExternalTestServer({"name": n, "url": f"http://localhost:1/{n}/"})
            for n in ("Busy", "Free")
        ]
        monkeypatch.setattr(config, "_collect_test_servers", lambda name, config_file: servers)
        t0 = time.monotonic()
        params = config._get_test_server_config(None, environment=False)
        assert time.monotonic() - t0 < 5
        assert params is not None and "Free" in params["url"]

    def test_fallback_uses_servers_without_session_lock(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pip-installed caldav has no tests/ and so no claim_server() on its servers."""
        from caldav import config

        server = config._ConfiguredServer("Lambda", {"url": "http://localhost:1/Lambda/"})
        monkeypatch.setattr(config, "_collect_test_servers", lambda name, config_file: [server])
        params = config._get_test_server_config(None, environment=False)
        assert params is not None and "Lambda" in params["url"]

    def test_fallback_releases_server_that_failed_to_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import fcntl

        from caldav import config

        class BrokenServer(base.ExternalTestServer):
            def start(self) -> None:
                self.claim()
                raise RuntimeError("does not start")

        broken = BrokenServer({"name": "Mu", "url": "http://localhost:1/Mu/"})
        free = base.ExternalTestServer({"name": "Nu", "url": "http://localhost:1/Nu/"})
        monkeypatch.setattr(
            config, "_collect_test_servers", lambda name, config_file: [broken, free]
        )
        params = config._get_test_server_config(None, environment=False)
        assert params is not None and "Nu" in params["url"]
        assert "Mu" not in base._session_locks
        with open(base._lock_path("Mu", ".session"), "a+") as other:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_claim_without_fcntl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No fcntl (Windows): no lock between processes, but claims still work."""
        import sys

        monkeypatch.setitem(sys.modules, "fcntl", None)
        assert base.TestServer.claim_server("Xi") is True
        assert base.TestServer.claim_server("Xi") is False

    def test_waiting_run_restarts_container_stopped_meanwhile(self, tmp_path: Path) -> None:
        """Collection saw the container up, but its owner stopped it before we got the lock."""
        counter = tmp_path / "runs"
        start_script = tmp_path / "start.sh"
        start_script.write_text(f"#!/bin/sh\necho run >> {counter}\n")
        start_script.chmod(0o755)

        class CountingServer(UnreachableDockerServer):
            def is_accessible(self) -> bool:
                return counter.exists()

        server = CountingServer({"name": "Eta", "docker_dir": str(tmp_path)})
        server.verify_docker = lambda: True  # type: ignore[method-assign]
        server._started = True  # as get_server_params() leaves it at collection
        server.start()
        assert counter.read_text().count("run") == 1
