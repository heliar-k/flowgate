import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llm_router.process import ProcessSupervisor
from llm_router.health import check_health_url


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

    def test_health_check_handles_network_error(self):
        with mock.patch("llm_router.health.urlopen", side_effect=OSError("boom")):
            self.assertFalse(check_health_url("http://127.0.0.1:1/", timeout=0.1))


if __name__ == "__main__":
    unittest.main()
