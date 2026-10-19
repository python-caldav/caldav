import os
import time

import pytest
import tzlocal


def pytest_configure(config):
    """Set PYTHON_CALDAV_DEBUGMODE=DEBUG_PDB automatically when --pdb is passed.

    This must happen in pytest_configure (before test collection) because
    caldav.lib.error reads the env var at module import time.
    """
    if config.option.usepdb and "PYTHON_CALDAV_DEBUGMODE" not in os.environ:
        os.environ["PYTHON_CALDAV_DEBUGMODE"] = "DEBUG_PDB"


@pytest.fixture
def process_tz(request, monkeypatch):
    """Run the test with the Python process in the time zone given by
    indirect parametrisation, e.g.
    @pytest.mark.parametrize("process_tz", ["America/New_York"], indirect=True)
    """
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    tzlocal.reload_localzone()
    yield request.param
    monkeypatch.undo()
    time.tzset()
    tzlocal.reload_localzone()


@pytest.fixture
def no_config_files(monkeypatch, tmp_path):
    """Keep the developer's own config files, CALDAV_*/CALENDARING_*
    variables and test-server mode out of the test: HOME is an empty directory, and the system
    paths point into it too."""
    import calendaring_config.discovery

    for name in list(os.environ):
        if name.startswith(("CALDAV_", "JMAP_", "CALENDARING_")):
            monkeypatch.delenv(name)
    monkeypatch.delenv("PYTHON_CALDAV_USE_TEST_SERVER", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(
        calendaring_config.discovery, "SYSTEM_PATHS", (tmp_path / "etc" / "calendar.conf",)
    )
    return tmp_path
