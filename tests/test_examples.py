import os
import sys
from datetime import datetime

from caldav.davclient import get_davclient


class TestExamples:
    def setup_method(self):
        os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = "1"
        sys.path.insert(0, ".")
        sys.path.insert(1, "..")

    def teardown_method(self):
        sys.path = sys.path[2:]
        del os.environ["PYTHON_CALDAV_USE_TEST_SERVER"]

    def test_get_events_example(self):
        with get_davclient() as client:
            mycal = client.principal().make_calendar(name="Test calendar")
            mycal.save_event(
                dtstart=datetime(2025, 5, 3, 10),
                dtend=datetime(2025, 5, 3, 11),
                summary="testevent",
            )
            from examples import get_events_example

            get_events_example.fetch_and_print()
