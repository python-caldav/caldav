"""
get_calendars() with config-file meta-sections, globs and per-section
calendar filters, in both sync and async mode, against an embedded Radicale.

https://github.com/python-caldav/caldav/issues/793
"""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from caldav import DAVClient, aio, get_calendars
from caldav.testing import RadicaleServer

from .test_servers.helpers import free_port

pytest.importorskip("radicale")


@pytest.fixture(scope="module")
def config_file(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    server = RadicaleServer({"port": free_port()})
    server.start()
    try:
        with DAVClient(url=server.url, username=server.username, password="") as client:
            principal = client.principal()
            for name in ("Work", "Home"):
                principal.make_calendar(name=name)
        section = f"  caldav_url: {server.url}/\n  caldav_username: {server.username}\n  caldav_password: x\n"
        path = tmp_path_factory.mktemp("config") / "calendar.conf"
        path.write_text(
            f"work:\n{section}  calendar_name: Work\n"
            f"home:\n{section}  calendar_name: Home\n"
            "both:\n  contains: [work, home]\n"
            f"badheaders:\n{section}  caldav_headers: notjson\n"
        )
        yield path
    finally:
        server.stop()


async def _async_names(**kwargs) -> list[str]:
    async with await aio.get_calendars(**kwargs) as calendars:
        return sorted([await c.get_display_name() for c in calendars])


def _names(mode: str, **kwargs) -> list[str]:
    kwargs.setdefault("environment", False)
    if mode == "async":
        return asyncio.run(_async_names(**kwargs))
    with get_calendars(**kwargs) as calendars:
        return sorted(c.get_display_name() for c in calendars)


@pytest.mark.parametrize("mode", ["sync", "async"])
class TestConfigSections:
    def test_section_calendar_filter(self, mode: str, config_file: Path) -> None:
        assert _names(mode, config_file=str(config_file), config_section="work") == ["Work"]

    def test_meta_section(self, mode: str, config_file: Path) -> None:
        names = _names(mode, config_file=str(config_file), config_section="both")
        assert names == ["Home", "Work"]

    def test_glob(self, mode: str, config_file: Path) -> None:
        assert _names(mode, config_file=str(config_file), config_section="h*") == ["Home"]

    def test_argument_overrides_section_filter(self, mode: str, config_file: Path) -> None:
        names = _names(
            mode, config_file=str(config_file), config_section="work", calendar_name="Home"
        )
        assert names == ["Home"]

    @pytest.mark.parametrize("section", ["typo", "x*", "badheaders"])
    def test_config_error_raises_whatever_raise_errors(
        self, mode: str, config_file: Path, section: str
    ) -> None:
        """A mistake in the configuration is not a server failure to skip."""
        with pytest.raises(ValueError, match="section|glob|match|headers"):
            _names(mode, config_file=str(config_file), config_section=section, raise_errors=False)
