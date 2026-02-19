"""CLI regression tests - service command group

Verifies that service commands maintain consistent exit codes and output formats.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowgate.cli import run_cli

import pytest


def write_minimal_config(path: Path) -> None:
    """Create a minimal test configuration file"""
    data = {
        "paths": {
            "runtime_dir": str(path.parent / "runtime"),
            "active_config": str(path.parent / "runtime" / "litellm.active.yaml"),
            "state_file": str(path.parent / "runtime" / "state.json"),
            "log_file": str(path.parent / "logs" / "routerctl.log"),
        },
        "services": {
            "litellm": {
                "host": "127.0.0.1",
                "port": 4000,
                "command": {"args": ["litellm"]},
            },
            "cliproxyapi_plus": {
                "host": "127.0.0.1",
                "port": 5000,
                "command": {"args": ["CLIProxyAPIPlus"]},
            },
        },
        "litellm_base": {"litellm_settings": {"num_retries": 1}},
        "profiles": {
            "reliability": {"litellm_settings": {"num_retries": 3}},
        },
        "auth": {
            "providers": {
                "codex": {
                    "auth_url_endpoint": "http://example.local/codex/auth-url",
                    "status_endpoint": "http://example.local/codex/status",
                },
            }
        },
        "secret_files": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(json.dumps(data), encoding="utf-8")
@pytest.mark.unit
class TestServiceCommandExitCodes(unittest.TestCase):
    """Regression tests for service command exit codes"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_minimal_config(self.cfg)

    def test_service_start_invalid_service_exit_code(self) -> None:
        """service start returns exit code 2 when service name is invalid"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", str(self.cfg), "service", "start", "nonexistent-service"],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 2, "Expected exit code 2 (config error)")
        error_output = err.getvalue()
        self.assertTrue(
            "unknown service" in error_output.lower(),
            f"Expected 'unknown service' error message, got: {error_output}",
        )

    def test_service_stop_invalid_service_exit_code(self) -> None:
        """service stop returns exit code 2 when service name is invalid"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", str(self.cfg), "service", "stop", "nonexistent-service"],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 2, "Expected exit code 2 (config error)")
        self.assertIn("unknown service", err.getvalue().lower())

    def test_service_restart_invalid_service_exit_code(self) -> None:
        """service restart returns exit code 2 when service name is invalid"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", str(self.cfg), "service", "restart", "nonexistent-service"],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 2, "Expected exit code 2 (config error)")
        self.assertIn("unknown service", err.getvalue().lower())

    def test_service_start_port_conflict_exit_code(self) -> None:
        """service start returns exit code 1 when port is already in use"""
        out = io.StringIO()
        err = io.StringIO()

        # Mock port check to simulate port conflict
        with mock.patch("flowgate.cli.commands.service._is_service_port_available", return_value=False):
            result = run_cli(
                ["--config", str(self.cfg), "service", "start", "litellm"],
                stdout=out,
                stderr=err,
            )

        self.assertEqual(result, 1, "Expected exit code 1 (runtime error)")
        error_output = err.getvalue()
        self.assertTrue(
            "port-in-use" in error_output or "port" in error_output.lower(),
            f"Expected port conflict error message, got: {error_output}",
        )

    def test_service_stop_not_running_exit_code(self) -> None:
        """service stop returns exit code 0 when service is not running (idempotent)"""
        out = io.StringIO()
        err = io.StringIO()

        # Mock supervisor to simulate service not running
        with mock.patch("flowgate.process.ProcessSupervisor.stop", return_value=False):
            result = run_cli(
                ["--config", str(self.cfg), "service", "stop", "litellm"],
                stdout=out,
                stderr=err,
            )

        # Service stop should be idempotent but might return 1 if stop fails
        self.assertIn(result, [0, 1], "Expected exit code 0 or 1")
        output = out.getvalue()
        self.assertIn("stop-failed", output, "Output should indicate stop-failed")

    def test_service_missing_command_argument_exit_code(self) -> None:
        """service command without action argument shows usage and returns error"""
        out = io.StringIO()
        err = io.StringIO()
        # argparse exits with SystemExit when required argument is missing
        with self.assertRaises(SystemExit) as cm:
            run_cli(
                ["--config", str(self.cfg), "service"],
                stdout=out,
                stderr=err,
            )
        # Should exit with code 2 (argparse error)

        self.assertEqual(cm.exception.code, 2, "Expected exit code 2 for missing subcommand")
@pytest.mark.unit
class TestServiceCommandOutput(unittest.TestCase):
    """Regression tests for service command output formats"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_minimal_config(self.cfg)

    def test_service_start_success_output_format(self) -> None:
        """service start success output includes service name and PID"""
        out = io.StringIO()

        # Mock supervisor to simulate successful start
        with mock.patch("flowgate.process.ProcessSupervisor.start", return_value=12345):
            result = run_cli(
                ["--config", str(self.cfg), "service", "start", "litellm"],
                stdout=out,
            )

        self.assertEqual(result, 0)
        output = out.getvalue()
        self.assertIn("litellm:started", output, "Output should contain 'litellm:started'")
        self.assertIn("pid=12345", output, "Output should contain 'pid=12345'")

    def test_service_stop_success_output_format(self) -> None:
        """service stop success output includes service name and stopped status"""
        out = io.StringIO()

        # Mock supervisor to simulate successful stop
        with mock.patch("flowgate.process.ProcessSupervisor.stop", return_value=True):
            result = run_cli(
                ["--config", str(self.cfg), "service", "stop", "litellm"],
                stdout=out,
            )

        self.assertEqual(result, 0)
        output = out.getvalue()
        self.assertIn("litellm:stopped", output, "Output should contain 'litellm:stopped'")

    def test_service_stop_failure_output_format(self) -> None:
        """service stop failure output includes service name and stop-failed status"""
        out = io.StringIO()

        # Mock supervisor to simulate stop failure
        with mock.patch("flowgate.process.ProcessSupervisor.stop", return_value=False):
            result = run_cli(
                ["--config", str(self.cfg), "service", "stop", "litellm"],
                stdout=out,
            )

        self.assertNotEqual(result, 0)
        output = out.getvalue()
        self.assertIn("litellm:stop-failed", output, "Output should contain 'litellm:stop-failed'")

    def test_service_restart_output_format(self) -> None:
        """service restart output includes service name and PID"""
        out = io.StringIO()

        # Mock supervisor to simulate successful restart
        with mock.patch("flowgate.process.ProcessSupervisor.restart", return_value=67890):
            result = run_cli(
                ["--config", str(self.cfg), "service", "restart", "litellm"],
                stdout=out,
            )

        self.assertEqual(result, 0)
        output = out.getvalue()
        self.assertIn("litellm:restarted", output, "Output should contain 'litellm:restarted'")
        self.assertIn("pid=67890", output, "Output should contain 'pid=67890'")

    def test_service_start_all_output_format(self) -> None:
        """service start all output includes all configured services"""
        out = io.StringIO()

        # Mock supervisor to simulate successful start of all services
        with mock.patch("flowgate.process.ProcessSupervisor.start", return_value=11111):
            result = run_cli(
                ["--config", str(self.cfg), "service", "start", "all"],
                stdout=out,
            )

        self.assertEqual(result, 0)
        output = out.getvalue()
        # Both services should appear in output
        self.assertIn("litellm:started", output, "Output should contain litellm")
        self.assertIn("cliproxyapi_plus:started", output, "Output should contain cliproxyapi_plus")
        # Both should show PIDs
        self.assertEqual(output.count("pid="), 2, "Both services should show PIDs")

    def test_service_port_conflict_output_format(self) -> None:
        """service start port conflict output includes port and host information"""
        out = io.StringIO()
        err = io.StringIO()

        # Mock port check to simulate port conflict
        with mock.patch("flowgate.cli.commands.service._is_service_port_available", return_value=False):
            result = run_cli(
                ["--config", str(self.cfg), "service", "start", "litellm"],
                stdout=out,
                stderr=err,
            )

        self.assertNotEqual(result, 0)
        error_output = err.getvalue()
        self.assertIn("litellm:", error_output, "Error should mention service name")
        self.assertIn("port-in-use", error_output, "Error should mention 'port-in-use'")
        self.assertIn("port=4000", error_output, "Error should include port number")


if __name__ == "__main__":
    unittest.main()
