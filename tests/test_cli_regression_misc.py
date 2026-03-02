"""CLI regression tests - diagnostic commands (non-profile).

Verifies that diagnostic commands maintain consistent exit codes and output
formats when using a config_version 3 (cliproxy-only) config.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from flowgate.cli import run_cli


def write_minimal_v3_config(root: Path) -> Path:
    """Create a minimal v3 config + cliproxyapi.yaml so load_router_config() succeeds."""
    cfg_dir = root / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    cliproxy_cfg = cfg_dir / "cliproxyapi.yaml"
    cliproxy_cfg.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 5000,
                "api-keys": ["sk-local-test"],
                "remote-management": {"secret-key": "x"},
            }
        ),
        encoding="utf-8",
    )

    runtime_dir = root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    flowgate_cfg = cfg_dir / "flowgate.yaml"
    flowgate_cfg.write_text(
        json.dumps(
            {
                "config_version": 3,
                "paths": {
                    "runtime_dir": str(runtime_dir),
                    "log_file": str(runtime_dir / "events.log"),
                },
                "cliproxyapi_plus": {"config_file": str(cliproxy_cfg)},
                "auth": {"providers": {}},
                "secret_files": [],
            }
        ),
        encoding="utf-8",
    )
    return flowgate_cfg


@pytest.mark.unit
class TestDiagnosticCommandRegression(unittest.TestCase):
    """Diagnostic command regression tests."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.config = write_minimal_v3_config(self.root)

    @mock.patch("flowgate.cli.health.ProcessSupervisor")
    @mock.patch("flowgate.cli.health.check_secret_file_permissions")
    def test_status_success(
        self, mock_check_perms: mock.Mock, mock_supervisor_cls: mock.Mock
    ) -> None:
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
        self.assertNotIn("current_profile=", output)
        self.assertNotIn("updated_at=", output)
        self.assertIn("services.cliproxyapi_plus_running=no", output)
        self.assertIn("cliproxyapi_plus_config=", output)
        self.assertIn("secret_permission_issues=0", output)

    @mock.patch("flowgate.cli.health.ProcessSupervisor")
    @mock.patch("flowgate.cli.health.check_http_health")
    @mock.patch("flowgate.cli.health.comprehensive_health_check")
    def test_health_all_services_healthy(
        self,
        mock_comprehensive: mock.Mock,
        mock_check_health: mock.Mock,
        mock_supervisor_cls: mock.Mock,
    ) -> None:
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = True

        mock_comprehensive.return_value = {
            "overall_status": "healthy",
            "status_counts": {"healthy": 1, "degraded": 0, "unhealthy": 0},
            "checks": {},
        }
        mock_check_health.return_value = {"ok": True, "status_code": 200, "error": None}

        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "health"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Service Health:", output)
        self.assertIn("cliproxyapi_plus: liveness=ok readiness=ok", output)
        self.assertEqual(output.count(": liveness="), 1)

    @mock.patch("flowgate.cli.health.ProcessSupervisor")
    @mock.patch("flowgate.cli.health.check_http_health")
    @mock.patch("flowgate.cli.health.comprehensive_health_check")
    def test_health_service_down_returns_nonzero(
        self,
        mock_comprehensive: mock.Mock,
        mock_check_health: mock.Mock,
        mock_supervisor_cls: mock.Mock,
    ) -> None:
        mock_supervisor = mock.Mock()
        mock_supervisor_cls.return_value = mock_supervisor
        mock_supervisor.is_running.return_value = False

        mock_comprehensive.return_value = {
            "overall_status": "healthy",
            "status_counts": {"healthy": 1, "degraded": 0, "unhealthy": 0},
            "checks": {},
        }
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
        self.assertIn("cliproxyapi_plus: liveness=fail readiness=fail", output)

    @mock.patch("flowgate.cli.health._is_executable_file", return_value=True)
    def test_doctor_runtime_exists(
        self,
        mock_is_executable: mock.Mock,
    ) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "doctor"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("doctor:config=pass", output)
        self.assertIn("doctor:runtime_dir=pass", output)
        self.assertIn("doctor:cliproxy_config=pass", output)

    @mock.patch("flowgate.cli.health._is_executable_file", return_value=False)
    def test_doctor_missing_binaries(self, mock_is_executable: mock.Mock) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        args = ["--config", str(self.config), "doctor"]

        exit_code = run_cli(args, stdout=stdout, stderr=stderr)

        self.assertNotEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("doctor:runtime_binaries=fail", output)


if __name__ == "__main__":
    unittest.main()
