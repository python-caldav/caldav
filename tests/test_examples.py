import sys
from datetime import datetime
from pathlib import Path

import pytest

from caldav import get_davclient

from .test_servers import client_context, has_test_servers

# Get the project root directory (parent of tests/)
_PROJECT_ROOT = Path(__file__).parent.parent


@pytest.mark.skipif(not has_test_servers(), reason="No test servers configured")
class TestExamples:
    @pytest.fixture(autouse=True)
    def setup_test_server(self):
        """Set up a test server config for get_davclient()."""
        # Add project root to find examples/
        sys.path.insert(0, str(_PROJECT_ROOT))

        # Start a test server and configure environment for get_davclient()
        self._test_context = client_context()
        self._conn = self._test_context.__enter__()

        yield

        # Cleanup
        self._test_context.__exit__(None, None, None)
        sys.path.remove(str(_PROJECT_ROOT))

    def test_get_events_example(self):
        with get_davclient() as dav_client:
            mycal = dav_client.principal().make_calendar(name="Test calendar")
            mycal.add_event(
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

        with get_davclient() as dav_client:
            mycal = dav_client.principal().make_calendar(name="Test calendar")
            collation_usage.run_examples()

    def test_rfc8764_test_conf(self):
        pass
