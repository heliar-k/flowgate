"""Error path tests for process management module.

This module tests error handling in process.py,
ensuring proper exception handling for process lifecycle operations.
"""

import os
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from flowgate.process import ProcessError, ProcessSupervisor


class TestProcessErrorHandling(unittest.TestCase):
    """Test process management error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.runtime_dir = Path(tempfile.mkdtemp())
        self.supervisor = ProcessSupervisor(self.runtime_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop any running processes
        for pid_file in self.supervisor.pid_dir.glob("*.pid"):
            service_name = pid_file.stem
            try:
                self.supervisor.stop(service_name, timeout=1)
            except Exception:
                pass

    def test_start_already_running_returns_existing_pid(self):
        """Test starting a service that is already running returns existing PID."""
        pid1 = self.supervisor.start(
            "test",
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )
        self.assertGreater(pid1, 0)
        self.assertTrue(self.supervisor.is_running("test"))

        # Try to start again
        pid2 = self.supervisor.start(
            "test",
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )
        self.assertEqual(pid1, pid2)

        self.supervisor.stop("test", timeout=2)

    def test_start_raises_when_running_without_pid(self):
        """Test RuntimeError when service appears running but PID unavailable.

        This is a theoretical edge case where is_running returns True but
        _read_pid returns None. In practice, this shouldn't happen with the
        current implementation, but the code has a check for it.
        """
        # Mock is_running to return True, but _read_pid to return None
        with mock.patch.object(self.supervisor, "is_running", return_value=True):
            with mock.patch.object(self.supervisor, "_read_pid", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    self.supervisor.start(
                        "test",
                        [sys.executable, "-c", "import time; time.sleep(30)"],
                    )
                self.assertIn("appears running but no pid is available", str(ctx.exception))

    def test_start_with_invalid_command(self):
        """Test exception when starting service with non-existent command."""
        with self.assertRaises(Exception):
            self.supervisor.start(
                "invalid",
                ["/non/existent/command", "--arg"],
            )

        # Verify event was recorded
        events_log = self.runtime_dir / "events.log"
        if events_log.exists():
            import json

            events = [
                json.loads(line)
                for line in events_log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            failed_events = [
                e for e in events if e["event"] == "service_start" and e["result"] == "failed"
            ]
            self.assertTrue(len(failed_events) > 0)

    def test_read_pid_corrupted_file(self):
        """Test reading PID file with non-numeric content."""
        pid_path = self.supervisor._pid_path("corrupted")
        pid_path.write_text("not-a-number", encoding="utf-8")

        pid = self.supervisor._read_pid("corrupted")
        self.assertIsNone(pid)

    def test_read_pid_empty_file(self):
        """Test reading PID file with empty content."""
        pid_path = self.supervisor._pid_path("empty")
        pid_path.write_text("", encoding="utf-8")

        pid = self.supervisor._read_pid("empty")
        self.assertIsNone(pid)

    def test_read_pid_nonexistent_file(self):
        """Test reading PID file that does not exist."""
        pid = self.supervisor._read_pid("nonexistent")
        self.assertIsNone(pid)

    def test_is_running_with_stale_pid_file(self):
        """Test is_running returns False when PID file exists but process is dead."""
        # Write a PID that is very unlikely to exist
        pid_path = self.supervisor._pid_path("stale")
        pid_path.write_text("999999", encoding="utf-8")

        self.assertFalse(self.supervisor.is_running("stale"))

    def test_stop_nonexistent_service(self):
        """Test stopping a service that is not running."""
        stopped = self.supervisor.stop("nonexistent", timeout=1)
        self.assertTrue(stopped)

    def test_stop_with_stale_pid(self):
        """Test stopping service with stale PID file."""
        # Write a dead PID
        pid_path = self.supervisor._pid_path("stale")
        pid_path.write_text("999999", encoding="utf-8")

        stopped = self.supervisor.stop("stale", timeout=1)
        self.assertTrue(stopped)
        self.assertFalse(pid_path.exists())

    def test_stop_timeout_and_kill(self):
        """Test stop uses SIGKILL when SIGTERM times out."""
        # Start a process that ignores SIGTERM
        pid = self.supervisor.start(
            "stubborn",
            [
                sys.executable,
                "-c",
                "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
            ],
        )
        self.assertTrue(self.supervisor.is_running("stubborn"))

        # Stop with very short timeout, should force SIGKILL
        stopped = self.supervisor.stop("stubborn", timeout=0.1)
        self.assertTrue(stopped)
        self.assertFalse(self.supervisor.is_running("stubborn"))

    def test_restart_fails_when_stop_fails(self):
        """Test RuntimeError when restart cannot stop the service."""
        # Mock stop to always return False (timeout)
        with mock.patch.object(self.supervisor, "stop", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                self.supervisor.restart(
                    "test",
                    [sys.executable, "-c", "import time; time.sleep(1)"],
                )
            self.assertIn("Failed to stop service before restart", str(ctx.exception))

    def test_restart_stops_and_starts_successfully(self):
        """Test successful restart stops old process and starts new one."""
        # Start initial process
        pid1 = self.supervisor.start(
            "test",
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )
        self.assertTrue(self.supervisor.is_running("test"))

        # Restart
        pid2 = self.supervisor.restart(
            "test",
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )
        self.assertNotEqual(pid1, pid2)
        self.assertTrue(self.supervisor.is_running("test"))

        # Verify old process is gone
        self.assertFalse(self.supervisor._is_pid_running(pid1))
        self.assertTrue(self.supervisor._is_pid_running(pid2))

        self.supervisor.stop("test", timeout=2)

    def test_record_event_handles_os_error(self):
        """Test record_event does not raise when logging fails."""
        # Make events log directory read-only
        events_log = self.runtime_dir / "events.log"
        events_log.parent.mkdir(parents=True, exist_ok=True)

        # Create a mock that raises OSError
        with mock.patch.object(Path, "open", side_effect=OSError("Permission denied")):
            # Should not raise
            self.supervisor.record_event(
                "test_event",
                service="test",
                result="success",
            )

    def test_is_pid_running_handles_permission_error(self):
        """Test _is_pid_running returns True when PermissionError is raised."""
        # os.kill with signal 0 raises PermissionError when process exists but no permission
        with mock.patch("os.kill", side_effect=PermissionError("No permission")):
            result = self.supervisor._is_pid_running(1)
            self.assertTrue(result)

    def test_is_pid_running_handles_process_lookup_error(self):
        """Test _is_pid_running returns False when ProcessLookupError is raised."""
        with mock.patch("os.kill", side_effect=ProcessLookupError("No such process")):
            result = self.supervisor._is_pid_running(999999)
            self.assertFalse(result)

    def test_stop_child_process_still_running(self):
        """Test stop when child process is in _children dict and still running."""
        # Start a process
        pid = self.supervisor.start(
            "child",
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )
        self.assertIn("child", self.supervisor._children)
        self.assertTrue(self.supervisor.is_running("child"))

        # Stop should clean up _children
        stopped = self.supervisor.stop("child", timeout=2)
        self.assertTrue(stopped)
        self.assertNotIn("child", self.supervisor._children)
        self.assertFalse(self.supervisor.is_running("child"))

    def test_stop_child_process_already_exited(self):
        """Test stop when child process is in _children but already exited."""
        # Start a process that exits immediately
        pid = self.supervisor.start(
            "quick",
            [sys.executable, "-c", "print('done')"],
        )
        self.assertIn("quick", self.supervisor._children)

        # Wait for process to exit
        time.sleep(0.5)

        # Stop should handle gracefully
        stopped = self.supervisor.stop("quick", timeout=1)
        self.assertTrue(stopped)
        self.assertNotIn("quick", self.supervisor._children)

    def test_stop_external_process_already_exited(self):
        """Test stop when PID file exists but process already exited."""
        # Write a PID file without starting through supervisor
        pid_path = self.supervisor._pid_path("external")
        # Use a PID that doesn't exist
        fake_pid = 999999
        pid_path.write_text(str(fake_pid), encoding="utf-8")

        stopped = self.supervisor.stop("external", timeout=1)
        self.assertTrue(stopped)
        self.assertFalse(pid_path.exists())

    def test_stop_sigterm_process_lookup_error(self):
        """Test stop handles ProcessLookupError when sending SIGTERM."""
        # Create PID file
        pid_path = self.supervisor._pid_path("gone")
        pid_path.write_text("999999", encoding="utf-8")

        # Mock _is_pid_running to return True once (for initial check), then False
        with mock.patch.object(
            self.supervisor,
            "_is_pid_running",
            side_effect=[True, False],
        ):
            # Mock os.kill to raise ProcessLookupError
            with mock.patch("os.kill", side_effect=ProcessLookupError):
                stopped = self.supervisor.stop("gone", timeout=1)
                self.assertTrue(stopped)
                self.assertFalse(pid_path.exists())

    def test_stop_sigkill_fails_permanently(self):
        """Test stop returns False when even SIGKILL fails.

        Note: This is very difficult to test in practice as SIGKILL should
        always succeed. We mock _is_pid_running to simulate a case where
        the process appears unkillable for the duration of the stop timeout.
        """
        # Start a real process
        pid = self.supervisor.start(
            "unkillable",
            [sys.executable, "-c", "import time; time.sleep(30)"],
        )

        # Remove from _children so stop() goes through the PID-based path
        self.supervisor._children.pop("unkillable", None)

        # Mock _is_pid_running to always return True during the entire stop operation
        with mock.patch.object(self.supervisor, "_is_pid_running", return_value=True):
            stopped = self.supervisor.stop("unkillable", timeout=0.05)
            self.assertFalse(stopped)

        # Clean up: stop for real using direct kill
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    unittest.main()
