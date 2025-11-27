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

    def test_basic_usage_examples(self):
        from examples import basic_usage_examples

        basic_usage_examples.run_examples()

    def test_collation(self):
        from examples import collation_usage

        with get_davclient() as client:
            mycal = client.principal().make_calendar(name="Test calendar")
            collation_usage.run_examples()

    def test_rfc8764_test_conf(self):
        from examples import rfc6764_test_conf
