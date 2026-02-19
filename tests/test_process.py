import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowgate.process import ProcessSupervisor
from flowgate.health import check_health_url

import pytest


@pytest.mark.unit
class ProcessSupervisorTests(unittest.TestCase):
    def test_start_and_stop_long_running_process(self):
        runtime_dir = Path(tempfile.mkdtemp())
        supervisor = ProcessSupervisor(runtime_dir)

        pid = supervisor.start(
            "litellm",
            [sys.executable, "-c", "import time; time.sleep(60)"],
            cwd=str(runtime_dir),
        )
        self.assertGreater(pid, 0)
        self.assertTrue(supervisor.is_running("litellm"))

        stopped = supervisor.stop("litellm", timeout=2)
        self.assertTrue(stopped)
        self.assertFalse(supervisor.is_running("litellm"))

        events_file = runtime_dir / "events.log"
        self.assertTrue(events_file.exists())
        events = [
            json.loads(line)
            for line in events_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(any(event["event"] == "service_start" for event in events))
        self.assertTrue(any(event["event"] == "service_stop" for event in events))
        for event in events:
            self.assertIn("service", event)
            self.assertIn("profile", event)
            self.assertIn("provider", event)
            self.assertIn("result", event)

    def test_health_check_handles_network_error(self):
        with mock.patch("flowgate.health.urlopen", side_effect=OSError("boom")):
            self.assertFalse(check_health_url("http://127.0.0.1:1/", timeout=0.1))


if __name__ == "__main__":
    unittest.main()
