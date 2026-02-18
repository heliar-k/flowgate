"""CLI regression tests - profile and diagnostic commands

Verifies that profile and diagnostic commands maintain consistent exit codes
and output formats.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowgate.cli import run_cli


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
            "balanced": {"litellm_settings": {"num_retries": 2}},
            "cost": {"litellm_settings": {"num_retries": 1}},
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
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_state_file(path: Path, profile: str = "reliability") -> None:
    """Create a minimal state file"""
    data = {
        "current_profile": profile,
        "updated_at": "2026-02-18T10:00:00Z",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class TestProfileCommandRegression(unittest.TestCase):
    """Profile command regression tests"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.config = self.root / "flowgate.yaml"
        write_minimal_config(self.config)

        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        state_file = runtime_dir / "state.json"
        write_state_file(state_file, "reliability")

    def test_profile_list_success(self) -> None:
        """profile list returns exit code 0 and lists all profiles"""
        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "profile", "list"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("reliability", output)
        self.assertIn("balanced", output)
        self.assertIn("cost", output)

    @mock.patch("flowgate.cli.ProcessSupervisor")
    @mock.patch("flowgate.cli.check_secret_file_permissions")
    def test_status_shows_current_profile(
        self, mock_check_perms: mock.Mock, mock_supervisor_cls: mock.Mock
    ) -> None:
        """status command displays current profile from state file"""
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = False
        mock_check_perms.return_value = []

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "status"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("current_profile=reliability", output)

    @mock.patch("flowgate.cli.ProcessSupervisor")
    def test_profile_set_success(self, mock_supervisor_cls: mock.Mock) -> None:
        """profile set switches to a valid profile and returns exit code 0"""
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = False

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "profile", "set", "balanced"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("profile=balanced", output)
        self.assertIn("active_config=", output)
        self.assertIn("state_file=", output)

    def test_profile_set_invalid_returns_nonzero(self) -> None:
        """profile set with nonexistent profile returns exit code 2"""
        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "profile", "set", "nonexistent"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 2)
        error_output = stderr.getvalue()
        self.assertIn("nonexistent", error_output)

    @mock.patch("flowgate.cli.ProcessSupervisor")
    def test_profile_set_with_litellm_running_restarts_service(
        self, mock_supervisor_cls: mock.Mock
    ) -> None:
        """profile set restarts LiteLLM if it's already running"""
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = True
        mock_supervisor.restart.return_value = 12345

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "profile", "set", "cost"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("profile=cost", output)
        self.assertIn("litellm:restarted", output)
        self.assertIn("pid=12345", output)
        mock_supervisor.restart.assert_called_once()


class TestDiagnosticCommandRegression(unittest.TestCase):
    """Diagnostic command regression tests"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.config = self.root / "flowgate.yaml"
        write_minimal_config(self.config)

        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        state_file = runtime_dir / "state.json"
        write_state_file(state_file, "reliability")

    @mock.patch("flowgate.cli.ProcessSupervisor")
    @mock.patch("flowgate.cli.check_secret_file_permissions")
    def test_status_success(
        self, mock_check_perms: mock.Mock, mock_supervisor_cls: mock.Mock
    ) -> None:
        """status command returns exit code 0 and displays service status"""
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = False
        mock_check_perms.return_value = []

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "status"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("current_profile=reliability", output)
        self.assertIn("updated_at=", output)
        self.assertIn("litellm_running=", output)
        self.assertIn("cliproxyapi_plus_running=", output)
        self.assertIn("secret_permission_issues=0", output)

    @mock.patch("flowgate.cli.ProcessSupervisor")
    @mock.patch("flowgate.cli.check_http_health")
    def test_health_all_services_healthy(
        self, mock_check_health: mock.Mock, mock_supervisor_cls: mock.Mock
    ) -> None:
        """health command returns exit code 0 when all services are healthy"""
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = True

        mock_check_health.return_value = {"ok": True, "status_code": 200, "error": None}

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "health"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("litellm:liveness=ok", output)
        self.assertIn("readiness=ok", output)
        self.assertIn("running=yes", output)
        self.assertIn("readiness_code=200", output)

    @mock.patch("flowgate.cli.ProcessSupervisor")
    @mock.patch("flowgate.cli.check_http_health")
    def test_health_service_down_returns_nonzero(
        self, mock_check_health: mock.Mock, mock_supervisor_cls: mock.Mock
    ) -> None:
        """health command returns exit code 1 when services are not running"""
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = False

        mock_check_health.return_value = {
            "ok": False,
            "status_code": None,
            "error": "connection-refused",
        }

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "health"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 1)
        output = stdout.getvalue()
        self.assertIn("liveness=fail", output)
        self.assertIn("readiness=fail", output)
        self.assertIn("running=no", output)

    @mock.patch("flowgate.cli._is_executable_file")
    def test_doctor_runtime_exists(self, mock_is_executable: mock.Mock) -> None:
        """doctor command checks runtime directory and binaries"""
        mock_is_executable.return_value = True

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "doctor"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("doctor:config=pass", output)
        self.assertIn("doctor:runtime_dir=pass", output)

    @mock.patch("flowgate.cli._is_executable_file")
    def test_doctor_missing_binaries(self, mock_is_executable: mock.Mock) -> None:
        """doctor command fails when runtime binaries are missing"""
        mock_is_executable.return_value = False

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "doctor"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertNotEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("doctor:runtime_binaries=fail", output)


if __name__ == "__main__":
    unittest.main()
