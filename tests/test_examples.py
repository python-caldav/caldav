import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from caldav import get_davclient
from .test_caldav import caldav_servers, client

# Get the project root directory (parent of tests/)
_PROJECT_ROOT = Path(__file__).parent.parent


@pytest.mark.skipif(not caldav_servers, reason="No test servers configured")
class TestExamples:
    @pytest.fixture(autouse=True)
    def setup_test_server(self):
        """Set up a test server config for get_davclient()."""
        # Add project root to find examples/
        sys.path.insert(0, str(_PROJECT_ROOT))

        # Use the first server (typically Radicale/Xandikos embedded servers)
        # The client() helper will start the server if needed via setup callback
        server_params = caldav_servers[0]

        # Start the server and keep it running throughout the test
        # by entering the context manager and not exiting until cleanup
        self._client = client(**server_params)
        self._conn = self._client.__enter__()

        # Create a temporary config file with testing_allowed: true
        config = {"testing_allowed": True}
        for key in ("username", "password", "proxy"):
            if key in server_params:
                config[f"caldav_{key}"] = server_params[key]
        config["caldav_url"] = server_params["url"]

        self._config_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"default": config}, self._config_file)
        self._config_file.close()

        os.environ["CALDAV_CONFIG_FILE"] = self._config_file.name
        os.environ["PYTHON_CALDAV_USE_TEST_SERVER"] = "1"

        yield

        # Cleanup
        self._client.__exit__(None, None, None)
        sys.path.remove(str(_PROJECT_ROOT))
        os.unlink(self._config_file.name)
        del os.environ["CALDAV_CONFIG_FILE"]
        del os.environ["PYTHON_CALDAV_USE_TEST_SERVER"]

    def test_get_events_example(self):
        with get_davclient() as dav_client:
            mycal = dav_client.principal().make_calendar(name="Test calendar")
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

        with get_davclient() as dav_client:
            mycal = dav_client.principal().make_calendar(name="Test calendar")
            collation_usage.run_examples()

    def test_rfc8764_test_conf(self):
        from examples import rfc6764_test_conf
