"""Tests for the error raised when no HTTP library is installed.

caldav needs an HTTP library, but which one is up to the user - see
``docs/source/http-libraries.rst``.  From v3.3.0 the dependency may be absent
from a plain ``pip install caldav``, so the failure has to explain itself
rather than surfacing as ``No module named 'requests'``.
"""

import ast
import pathlib
import subprocess
import sys
import textwrap

import pytest

from caldav.lib.http_libraries import (
    ASYNC_CANDIDATES,
    ASYNC_HTTPX_CANDIDATES,
    DOCS_URL,
    SYNC_CANDIDATES,
    no_http_library_error,
    required_library_error,
)

## Modules that reach the HTTP-library import on their own, so the message has
## to come out of their own import.  caldav.jmap.client and caldav.jmap.session
## are deliberately absent: importing either runs caldav/jmap/__init__.py
## first, which imports async_client -> http_sync, so the error never comes
## from the module under test and the case would pass even if the module were
## reverted.  TestOnlyOneModuleImportsTheHTTPLibrary is what covers those two.
SYNC_MODULES = [
    "caldav.davclient",
    "caldav.discovery",
    "caldav.requests",
    "caldav.testing",
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


class TestOnlyOneModuleImportsTheHTTPLibrary:
    """The HTTP library is imported in one place, by design.

    Before this was enforced, six modules carried their own copy of the
    "niquests, or else requests" try/except - and every one of them had to be
    found and fixed when the "no HTTP library at all" case appeared.
    """

    ## async_davclient owns the httpx-family selection (a different set of
    ## libraries and a different fallback order), so it imports its own.
    ALLOWED = {
        "caldav/lib/http_sync.py",
        "caldav/async_davclient.py",
    }
    HTTP_LIBRARIES = {"niquests", "requests", "httpx", "httpx2", "httpxyz"}

    def _direct_importers(self) -> dict[str, set[str]]:
        """Map source file -> HTTP libraries it imports by name."""
        root = pathlib.Path(__file__).parent.parent
        found: dict[str, set[str]] = {}
        for path in sorted((root / "caldav").rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            tree = ast.parse(path.read_text(), filename=rel)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom):
                    ## A relative import cannot name a third-party library.
                    names = {node.module.split(".")[0]} if node.module and not node.level else set()
                else:
                    continue
                hits = names & self.HTTP_LIBRARIES
                if hits:
                    found.setdefault(rel, set()).update(hits)
        return found

    def test_no_module_outside_the_allowlist_imports_one(self) -> None:
        offenders = {
            path: sorted(libs)
            for path, libs in self._direct_importers().items()
            if path not in self.ALLOWED
        }
        assert not offenders, (
            "these modules import an HTTP library directly; import the symbols "
            f"from caldav.lib.http_sync instead: {offenders}"
        )

    def test_the_allowlisted_modules_really_do_import_one(self) -> None:
        """Guard against the allowlist going stale."""
        importers = self._direct_importers()
        for path in self.ALLOWED:
            assert path in importers, f"{path} no longer imports an HTTP library"


class TestSharedCandidateLists:
    """The point of the shared lists is that there is one copy."""

    def test_async_davclient_uses_the_shared_httpx_list(self) -> None:
        """A literal re-spelled here and in http_libraries drifts silently - and
        the tests below take their blocklist from the shared copy, so a drift
        would make them block the wrong libraries."""
        from caldav.async_davclient import _ASYNC_HTTPX_CANDIDATES

        assert _ASYNC_HTTPX_CANDIDATES is ASYNC_HTTPX_CANDIDATES

    def test_async_candidates_is_niquests_then_the_httpx_family(self) -> None:
        """Pins the literal, which now lives in exactly one place."""
        assert ASYNC_CANDIDATES == ("niquests", "httpx2", "httpxyz", "httpx")


class TestRequiredLibraryMessage:
    """A library that has no fallback needs different wording from "none of
    them is installed" - the sync stack may well be running on requests."""

    def test_names_the_required_library(self) -> None:
        message = required_library_error("niquests", "the async JMAP client")
        assert "niquests" in message
        assert "the async JMAP client" in message

    def test_does_not_claim_nothing_is_installed(self) -> None:
        message = required_library_error("niquests", "the async JMAP client")
        assert "none of the supported" not in message

    def test_still_points_at_the_extra_and_the_docs(self) -> None:
        message = required_library_error("niquests", "the async JMAP client")
        assert "caldav[niquests]" in message
        assert DOCS_URL in message

    def test_jmap_async_client_uses_it(self) -> None:
        """Only niquests blocked: the sync stack is fine on requests, so the
        "nothing is installed" wording would be a lie."""
        message = _import_with_libraries_blocked("caldav.jmap.async_client", ("niquests",))
        assert "none of the supported" not in message
        assert "niquests" in message


class TestAsyncOnlyInstall:
    """niquests gone, an httpx present, requests gone - the shape an async-only
    consumer gets once caldav stops depending on niquests."""

    def test_importing_the_async_client_works(self) -> None:
        code = textwrap.dedent(
            """
            import sys

            class Blocker:
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.split(".")[0] in ("niquests", "requests"):
                        raise ImportError("blocked by the test: " + fullname)
                    return None

            sys.meta_path.insert(0, Blocker())
            import caldav.async_davclient as a
            assert a._USE_HTTPX, "expected the httpx family to be selected"
            print("ok")
            """
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode == 0, (
            "an httpx-only install must not need the sync HTTP library:\n"
            + (result.stderr or result.stdout)
        )


class TestBackwardCompatibleReExports:
    """``caldav.davclient`` used to do the HTTP-library import itself, so a few
    of the library's own names have been reachable from it for years.  The
    import moved to :mod:`caldav.lib.http_sync` in v3.3.0 and the names stayed
    behind as re-exports; nothing in the tree uses them, which is exactly why
    they need a test - an unused-import sweep would otherwise delete them and
    silently break whoever imports them."""

    def test_the_use_flags_resolve(self) -> None:
        """The CI fallback jobs import these two from here by hand."""
        from caldav.davclient import _USE_NIQUESTS, _USE_REQUESTS

        assert _USE_NIQUESTS or _USE_REQUESTS

    def test_the_use_flags_are_the_shared_ones(self) -> None:
        from caldav import davclient
        from caldav.lib import http_sync

        assert davclient._USE_NIQUESTS is http_sync.USE_NIQUESTS
        assert davclient._USE_REQUESTS is http_sync.USE_REQUESTS

    def test_response_resolves(self) -> None:
        """Importable from davclient since 2023 and shipped in v3.0 and v3.2;
        not part of the documented API, kept so removing it is a decision
        rather than an accident."""
        from caldav.davclient import Response
        from caldav.lib.http_sync import Response as SharedResponse

        assert Response is SharedResponse
