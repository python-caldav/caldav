"""Tests for the test server base classes."""

import subprocess
from pathlib import Path

import pytest

from .base import DockerTestServer


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
