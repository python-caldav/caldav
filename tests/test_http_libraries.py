"""Tests for the error raised when no HTTP library is installed.

caldav needs an HTTP library, but which one is up to the user - see
``docs/source/http-libraries.rst``.  From v3.3.0 the dependency may be absent
from a plain ``pip install caldav``, so the failure has to explain itself
rather than surfacing as ``No module named 'requests'``.
"""

import subprocess
import sys
import textwrap

import pytest

from caldav.lib.http_libraries import (
    ASYNC_CANDIDATES,
    DOCS_URL,
    SYNC_CANDIDATES,
    no_http_library_error,
)

## Every module carrying the "niquests, or else requests" fallback.  All of
## them are reachable without touching the others, so all of them have to
## explain themselves.
SYNC_MODULES = [
    "caldav.davclient",
    "caldav.discovery",
    "caldav.requests",
    "caldav.testing",
    "caldav.jmap.client",
    "caldav.jmap.session",
]

_BLOCK_AND_IMPORT = textwrap.dedent(
    """
    import sys

    class Blocker:
        def __init__(self, names):
            self.names = names

        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in self.names:
                raise ImportError("blocked by the test: " + fullname)
            return None

    sys.meta_path.insert(0, Blocker({names!r}))
    try:
        import {module}
    except ImportError as e:
        print(str(e))
        sys.exit(0)
    sys.exit("expected an ImportError from {module}")
    """
)


def _import_with_libraries_blocked(module: str, names: tuple[str, ...]) -> str:
    """Import `module` in a subprocess with `names` unimportable, return the error."""
    result = subprocess.run(
        [sys.executable, "-c", _BLOCK_AND_IMPORT.format(module=module, names=set(names))],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout


class TestNoHTTPLibraryMessage:
    """The message itself - it has one job, so it is spelled out here."""

    @pytest.mark.parametrize("candidates", [SYNC_CANDIDATES, ASYNC_CANDIDATES])
    def test_names_every_candidate(self, candidates: tuple[str, ...]) -> None:
        message = no_http_library_error(candidates)
        for name in candidates:
            assert name in message

    def test_recommends_niquests(self) -> None:
        assert "pip install niquests" in no_http_library_error(SYNC_CANDIDATES)

    def test_points_at_the_extra(self) -> None:
        """The whole point: tell a downstream packager how to declare it."""
        assert "caldav[niquests]" in no_http_library_error(SYNC_CANDIDATES)

    def test_links_the_documentation(self) -> None:
        assert DOCS_URL in no_http_library_error(SYNC_CANDIDATES)

    def test_says_which_mode(self) -> None:
        assert "async" in no_http_library_error(ASYNC_CANDIDATES, mode="async")


class TestImportWithoutAnyHTTPLibrary:
    """The real import paths, with the libraries genuinely unavailable."""

    @pytest.mark.parametrize("module", SYNC_MODULES)
    def test_sync_module_explains_itself(self, module: str) -> None:
        message = _import_with_libraries_blocked(module, SYNC_CANDIDATES)
        assert "caldav[niquests]" in message
        assert DOCS_URL in message
        assert "No module named" not in message

    def test_async_module_explains_itself(self) -> None:
        message = _import_with_libraries_blocked("caldav.async_davclient", ASYNC_CANDIDATES)
        assert "caldav[niquests]" in message
        assert DOCS_URL in message
