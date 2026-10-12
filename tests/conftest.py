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
