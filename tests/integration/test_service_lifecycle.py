"""Integration tests: service lifecycle (start / stop / restart).

These tests exercise ProcessSupervisor with real subprocess management
using mock commands (``python -c "import time; time.sleep(120)"``).
They do NOT require LiteLLM or CLIProxyAPIPlus binaries.

Run with:
    pytest tests/integration/test_service_lifecycle.py -v -m integration
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

import pytest

from flowgate.process import ProcessSupervisor

from .base import IntegrationTestBase


_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(120)"]
_FAST_EXIT_CMD = [sys.executable, "-c", "import sys; sys.exit(0)"]


@pytest.mark.integration
class TestServiceStart(IntegrationTestBase):
    """Tests for ProcessSupervisor.start()."""

    def _make_supervisor(self) -> ProcessSupervisor:
        return ProcessSupervisor(self.root / "runtime")

    def test_start_returns_positive_pid(self) -> None:
        """Starting a mock service returns a valid PID > 0."""
        sv = self._make_supervisor()
        pid = sv.start("svc-a", _SLEEP_CMD)
        try:
            self.assertGreater(pid, 0)
        finally:
            sv.stop("svc-a", timeout=3)

    def test_started_service_is_running(self) -> None:
        """is_running() returns True immediately after start."""
        sv = self._make_supervisor()
        sv.start("svc-b", _SLEEP_CMD)
        try:
            self.assertTrue(sv.is_running("svc-b"))
        finally:
            sv.stop("svc-b", timeout=3)

    def test_double_start_returns_existing_pid(self) -> None:
        """Starting an already-running service returns the same PID."""
        sv = self._make_supervisor()
        pid1 = sv.start("svc-c", _SLEEP_CMD)
        try:
            pid2 = sv.start("svc-c", _SLEEP_CMD)
            self.assertEqual(pid1, pid2)
        finally:
            sv.stop("svc-c", timeout=3)

    def test_start_records_service_start_event(self) -> None:
        """A service_start event is written to events.log on first start."""
        sv = self._make_supervisor()
        sv.start("svc-d", _SLEEP_CMD)
        try:
            events = self.read_events()
            start_events = [e for e in events if e["event"] == "service_start"]
            self.assertTrue(len(start_events) >= 1)
            self.assertEqual(start_events[0]["service"], "svc-d")
            self.assertEqual(start_events[0]["result"], "success")
        finally:
            sv.stop("svc-d", timeout=3)

    def test_double_start_records_already_running_event(self) -> None:
        """Starting a running service records result=already-running in the log."""
        sv = self._make_supervisor()
        sv.start("svc-e", _SLEEP_CMD)
        try:
            sv.start("svc-e", _SLEEP_CMD)
            events = self.read_events()
            dup_events = [
                e
                for e in events
                if e["event"] == "service_start" and e.get("result") == "already-running"
            ]
            self.assertTrue(len(dup_events) >= 1)
        finally:
            sv.stop("svc-e", timeout=3)

    def test_pid_file_created_on_start(self) -> None:
        """A PID file is created in the pids directory after start."""
        sv = self._make_supervisor()
        sv.start("svc-f", _SLEEP_CMD)
        try:
            pid_file = self.root / "runtime" / "pids" / "svc-f.pid"
            self.assertTrue(pid_file.exists())
            pid_text = pid_file.read_text(encoding="utf-8").strip()
            self.assertTrue(pid_text.isdigit())
        finally:
            sv.stop("svc-f", timeout=3)


@pytest.mark.integration
class TestServiceStop(IntegrationTestBase):
    """Tests for ProcessSupervisor.stop()."""

    def _make_supervisor(self) -> ProcessSupervisor:
        return ProcessSupervisor(self.root / "runtime")

    def test_stop_terminates_running_service(self) -> None:
        """stop() terminates a running service and returns True."""
        sv = self._make_supervisor()
        sv.start("svc-g", _SLEEP_CMD)
        self.assertTrue(sv.is_running("svc-g"))

        result = sv.stop("svc-g", timeout=5)
        self.assertTrue(result)
        self.assertFalse(sv.is_running("svc-g"))

    def test_stop_records_service_stop_event(self) -> None:
        """A service_stop event is written to events.log after stop."""
        sv = self._make_supervisor()
        sv.start("svc-h", _SLEEP_CMD)
        sv.stop("svc-h", timeout=5)

        events = self.read_events()
        stop_events = [e for e in events if e["event"] == "service_stop"]
        self.assertTrue(len(stop_events) >= 1)
        self.assertEqual(stop_events[0]["service"], "svc-h")

    def test_stop_nonexistent_service_returns_true(self) -> None:
        """Stopping a service that was never started returns True (idempotent)."""
        sv = self._make_supervisor()
        result = sv.stop("no-such-service", timeout=2)
        self.assertTrue(result)

    def test_stop_removes_pid_file(self) -> None:
        """The PID file is removed after a service is stopped."""
        sv = self._make_supervisor()
        sv.start("svc-i", _SLEEP_CMD)
        sv.stop("svc-i", timeout=5)

        pid_file = self.root / "runtime" / "pids" / "svc-i.pid"
        self.assertFalse(pid_file.exists())

    def test_stop_stale_pid_file_returns_true(self) -> None:
        """Stopping a service whose PID is no longer alive returns True."""
        sv = self._make_supervisor()
        # Write a PID that is guaranteed to not exist
        pid_dir = self.root / "runtime" / "pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        (pid_dir / "ghost-svc.pid").write_text("999999999", encoding="utf-8")

        result = sv.stop("ghost-svc", timeout=2)
        self.assertTrue(result)


@pytest.mark.integration
class TestServiceRestart(IntegrationTestBase):
    """Tests for ProcessSupervisor.restart()."""

    def _make_supervisor(self) -> ProcessSupervisor:
        return ProcessSupervisor(self.root / "runtime")

    def test_restart_stops_old_and_starts_new(self) -> None:
        """restart() terminates the old process and returns a new PID."""
        sv = self._make_supervisor()
        pid1 = sv.start("svc-j", _SLEEP_CMD)
        self.assertTrue(sv.is_running("svc-j"))

        pid2 = sv.restart("svc-j", _SLEEP_CMD)
        try:
            self.assertGreater(pid2, 0)
            self.assertTrue(sv.is_running("svc-j"))
            # PIDs should differ (new process was spawned)
            self.assertNotEqual(pid1, pid2)
        finally:
            sv.stop("svc-j", timeout=3)

    def test_restart_records_restart_event(self) -> None:
        """A service_restart event is written to events.log."""
        sv = self._make_supervisor()
        sv.start("svc-k", _SLEEP_CMD)
        sv.restart("svc-k", _SLEEP_CMD)
        try:
            events = self.read_events()
            restart_events = [e for e in events if e["event"] == "service_restart"]
            self.assertTrue(len(restart_events) >= 1)
            self.assertEqual(restart_events[0]["result"], "success")
        finally:
            sv.stop("svc-k", timeout=3)

    def test_restart_service_that_was_never_started(self) -> None:
        """restart() on a never-started service still produces a running process."""
        sv = self._make_supervisor()
        pid = sv.restart("svc-l", _SLEEP_CMD)
        try:
            self.assertGreater(pid, 0)
            self.assertTrue(sv.is_running("svc-l"))
        finally:
            sv.stop("svc-l", timeout=3)


@pytest.mark.integration
class TestServiceLifecycleEndToEnd(IntegrationTestBase):
    """End-to-end lifecycle: start → health-check state → stop."""

    def _make_supervisor(self) -> ProcessSupervisor:
        return ProcessSupervisor(self.root / "runtime")

    def test_full_lifecycle_start_check_stop(self) -> None:
        """Full flow: start a service, confirm it is running, then stop it."""
        sv = self._make_supervisor()
        pid = sv.start("e2e-svc", _SLEEP_CMD)

        # After start: running
        self.assertGreater(pid, 0)
        self.assertTrue(sv.is_running("e2e-svc"))

        # Graceful stop
        stopped = sv.stop("e2e-svc", timeout=5)
        self.assertTrue(stopped)
        self.assertFalse(sv.is_running("e2e-svc"))

    def test_two_independent_services_lifecycle(self) -> None:
        """Two services can be managed independently by the same supervisor."""
        sv = self._make_supervisor()
        pid_a = sv.start("alpha", _SLEEP_CMD)
        pid_b = sv.start("beta", _SLEEP_CMD)
        try:
            self.assertTrue(sv.is_running("alpha"))
            self.assertTrue(sv.is_running("beta"))
            self.assertNotEqual(pid_a, pid_b)
        finally:
            sv.stop("alpha", timeout=3)
            sv.stop("beta", timeout=3)

        self.assertFalse(sv.is_running("alpha"))
        self.assertFalse(sv.is_running("beta"))

    def test_events_log_contains_all_lifecycle_events(self) -> None:
        """Events log records start and stop for the full lifecycle."""
        sv = self._make_supervisor()
        sv.start("log-svc", _SLEEP_CMD)
        sv.stop("log-svc", timeout=5)

        events = self.read_events()
        event_types = {e["event"] for e in events}
        self.assertIn("service_start", event_types)
        self.assertIn("service_stop", event_types)


@pytest.mark.integration
class TestEventLogIntegrity(IntegrationTestBase):
    """Verify that the event log is valid JSON-lines after multiple operations."""

    def test_events_log_is_valid_json_lines(self) -> None:
        """Every line in events.log is a valid JSON object with required fields."""
        sv = ProcessSupervisor(self.root / "runtime")
        sv.start("jl-svc", _SLEEP_CMD)
        sv.stop("jl-svc", timeout=5)

        events_path = self.root / "runtime" / "events.log"
        self.assertTrue(events_path.exists())
        lines = [l for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertGreater(len(lines), 0)

        required_fields = {"event", "service", "result", "timestamp"}
        for line in lines:
            record = json.loads(line)  # raises if invalid JSON
            for field in required_fields:
                self.assertIn(field, record, f"Missing field '{field}' in event: {record}")

    def test_multiple_services_events_are_distinct(self) -> None:
        """Events from different services are individually recorded and distinguishable."""
        sv = ProcessSupervisor(self.root / "runtime")
        sv.start("svc-x", _SLEEP_CMD)
        sv.start("svc-y", _SLEEP_CMD)
        try:
            events = self.read_events()
            services = {e["service"] for e in events}
            self.assertIn("svc-x", services)
            self.assertIn("svc-y", services)
        finally:
            sv.stop("svc-x", timeout=3)
            sv.stop("svc-y", timeout=3)


if __name__ == "__main__":
    unittest.main()
