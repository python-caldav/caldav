import os


def pytest_configure(config):
    """Set PYTHON_CALDAV_DEBUGMODE=DEBUG_PDB automatically when --pdb is passed.

    This must happen in pytest_configure (before test collection) because
    caldav.lib.error reads the env var at module import time.
    """
    if config.option.usepdb and "PYTHON_CALDAV_DEBUGMODE" not in os.environ:
        os.environ["PYTHON_CALDAV_DEBUGMODE"] = "DEBUG_PDB"
