"""
Tests that ``import caldav`` is lazy and does not pull in heavy dependencies
(niquests, icalendar, lxml) until they are actually needed.

Each test spawns a subprocess so the import state is pristine.
"""

import subprocess
import sys
import textwrap

import pytest

PYTHON = sys.executable


def _run(code: str) -> subprocess.CompletedProcess:
    """Run *code* in a fresh Python subprocess."""
    return subprocess.run(
        [PYTHON, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestLazyImport:
    def test_import_does_not_load_niquests(self):
        r = _run("""\
            import caldav, sys
            for mod in ("niquests", "requests"):
                assert mod not in sys.modules, f"{mod} loaded eagerly"
        """)
        assert r.returncode == 0, r.stderr

    def test_import_does_not_load_icalendar(self):
        r = _run("""\
            import caldav, sys
            assert "icalendar" not in sys.modules, "icalendar loaded eagerly"
        """)
        assert r.returncode == 0, r.stderr

    def test_import_does_not_load_lxml(self):
        r = _run("""\
            import caldav, sys
            assert "lxml" not in sys.modules, "lxml loaded eagerly"
        """)
        assert r.returncode == 0, r.stderr

    def test_version_available_without_heavy_imports(self):
        r = _run("""\
            import caldav, sys
            v = caldav.__version__
            assert isinstance(v, str)
            for mod in ("niquests", "requests", "icalendar", "lxml"):
                assert mod not in sys.modules, f"{mod} loaded by __version__"
        """)
        assert r.returncode == 0, r.stderr

    def test_davclient_importable(self):
        r = _run("""\
            from caldav import DAVClient
            assert callable(DAVClient)
        """)
        assert r.returncode == 0, r.stderr

    def test_calendar_importable(self):
        r = _run("""\
            from caldav import Calendar
            assert callable(Calendar)
        """)
        assert r.returncode == 0, r.stderr

    def test_event_importable(self):
        r = _run("""\
            from caldav import Event, Todo, Journal, FreeBusy
        """)
        assert r.returncode == 0, r.stderr

    def test_principal_importable(self):
        r = _run("""\
            from caldav import Principal
            assert callable(Principal)
        """)
        assert r.returncode == 0, r.stderr

    def test_searcher_importable(self):
        r = _run("""\
            from caldav import CalDAVSearcher
            assert callable(CalDAVSearcher)
        """)
        assert r.returncode == 0, r.stderr

    def test_error_submodule(self):
        r = _run("""\
            import caldav
            err = caldav.error
            assert hasattr(err, "NotFoundError")
        """)
        assert r.returncode == 0, r.stderr

    def test_dir_includes_lazy_names(self):
        r = _run("""\
            import caldav
            names = dir(caldav)
            for expected in ("DAVClient", "Calendar", "Event", "Principal",
                             "CalDAVSearcher", "error", "__version__"):
                assert expected in names, f"{expected!r} missing from dir(caldav)"
        """)
        assert r.returncode == 0, r.stderr

    def test_unknown_attribute_raises(self):
        r = _run("""\
            import caldav
            try:
                caldav.NoSuchThing
                raise SystemExit("should have raised AttributeError")
            except AttributeError:
                pass
        """)
        assert r.returncode == 0, r.stderr

    def test_get_functions_importable(self):
        r = _run("""\
            from caldav import get_calendar, get_calendars, get_davclient
            assert callable(get_calendar)
            assert callable(get_calendars)
            assert callable(get_davclient)
        """)
        assert r.returncode == 0, r.stderr

    def test_collection_types_importable(self):
        r = _run("""\
            from caldav import (
                CalendarCollection, CalendarResult, CalendarSet,
                DAVObject, CalendarObjectResource,
                ScheduleMailbox, ScheduleInbox, ScheduleOutbox,
                SynchronizableCalendarObjectCollection,
            )
        """)
        assert r.returncode == 0, r.stderr
