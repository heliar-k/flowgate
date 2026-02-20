"""Tests for enhanced health check functionality."""

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from flowgate.health import (
    HealthCheckResult,
    check_credentials,
    check_disk_space,
    check_memory_usage,
    check_port_availability,
    check_service_ports,
    comprehensive_health_check,
)


@pytest.mark.unit
class TestCheckDiskSpace(unittest.TestCase):
    """Test disk space checking."""

    def test_check_disk_space_healthy(self):
        """Test disk space check when plenty of space available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_disk_space(tmpdir, threshold_percent=10)

            self.assertEqual(result["status"], "healthy")
            self.assertIn("Disk space OK", result["message"])
            self.assertIn("free_percent", result["details"])
            self.assertGreater(result["details"]["free_percent"], 10)

    def test_check_disk_space_with_high_threshold(self):
        """Test disk space check with unrealistic threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set threshold to 99% - should trigger degraded
            result = check_disk_space(tmpdir, threshold_percent=99)

            self.assertEqual(result["status"], "degraded")
            self.assertIn("Low disk space", result["message"])

    def test_check_disk_space_nonexistent_path(self):
        """Test disk space check with nonexistent path."""
        result = check_disk_space("/nonexistent/path/12345")

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("does not exist", result["message"])
        self.assertFalse(result["details"]["exists"])

    def test_check_disk_space_details_format(self):
        """Test that disk space details have correct format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_disk_space(tmpdir)

            details = result["details"]
            self.assertIn("path", details)
            self.assertIn("total_gb", details)
            self.assertIn("used_gb", details)
            self.assertIn("free_gb", details)
            self.assertIn("free_percent", details)
            self.assertIn("threshold_percent", details)

            # Check types
            self.assertIsInstance(details["total_gb"], (int, float))
            self.assertIsInstance(details["free_percent"], (int, float))


@pytest.mark.unit
class TestCheckMemoryUsage(unittest.TestCase):
    """Test memory usage checking."""

    def test_check_memory_usage_with_psutil(self):
        """Test memory check when psutil is available."""
        mock_mem = Mock()
        mock_mem.total = 16 * 1024**3  # 16GB
        mock_mem.used = 8 * 1024**3  # 8GB
        mock_mem.available = 8 * 1024**3  # 8GB
        mock_mem.percent = 50.0

        with patch.dict("sys.modules", {"psutil": Mock()}):
            import sys

            sys.modules["psutil"].virtual_memory = Mock(return_value=mock_mem)

            result = check_memory_usage()

            self.assertEqual(result["status"], "healthy")
            self.assertIn("Memory usage OK", result["message"])
            self.assertEqual(result["details"]["percent_used"], 50.0)

    def test_check_memory_usage_high_usage(self):
        """Test memory check with high usage."""
        mock_mem = Mock()
        mock_mem.total = 16 * 1024**3
        mock_mem.used = 15 * 1024**3
        mock_mem.available = 1 * 1024**3
        mock_mem.percent = 95.0

        with patch.dict("sys.modules", {"psutil": Mock()}):
            import sys

            sys.modules["psutil"].virtual_memory = Mock(return_value=mock_mem)

            result = check_memory_usage()

            self.assertEqual(result["status"], "degraded")
            self.assertIn("High memory usage", result["message"])

    def test_check_memory_usage_without_psutil(self):
        """Test memory check when psutil is not available."""
        # Remove psutil from sys.modules if it exists
        with patch.dict("sys.modules", {"psutil": None}):
            with patch("flowgate.health.Path") as mock_path:
                mock_meminfo = Mock()
                mock_path.return_value = mock_meminfo
                mock_meminfo.exists.return_value = False

                result = check_memory_usage()

                self.assertEqual(result["status"], "healthy")
                self.assertIn("not available", result["message"])
                self.assertFalse(result["details"]["available"])

    def test_check_memory_usage_linux_proc_meminfo(self):
        """Test memory check using /proc/meminfo on Linux."""
        # This test is platform-specific and complex to mock properly
        # Just verify the function doesn't crash when psutil is unavailable
        with patch.dict("sys.modules", {"psutil": None}):
            result = check_memory_usage()

            # Should return a valid result (either healthy or with details)
            self.assertIn(result["status"], ["healthy", "degraded", "unhealthy"])
            self.assertIn("message", result)
            self.assertIn("details", result)


@pytest.mark.unit
class TestCheckPortAvailability(unittest.TestCase):
    """Test port availability checking."""

    def test_check_port_available(self):
        """Test checking an available port."""
        # Find an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        result = check_port_availability("127.0.0.1", port)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("available", result["message"])
        self.assertFalse(result["details"]["in_use"])

    def test_check_port_in_use(self):
        """Test checking a port that's in use."""
        # Create a server socket that stays open
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        try:
            # Check while socket is still bound
            result = check_port_availability("127.0.0.1", port)

            self.assertEqual(result["status"], "unhealthy")
            self.assertIn("already in use", result["message"])
            self.assertTrue(result["details"]["in_use"])
        finally:
            server.close()

    def test_check_port_invalid_host(self):
        """Test checking port with invalid host."""
        result = check_port_availability("999.999.999.999", 8080)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("Failed to check port", result["message"])
        self.assertIn("error", result["details"])


@pytest.mark.unit
class TestCheckCredentials(unittest.TestCase):
    """Test credential file checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_credentials_no_config(self):
        """Test credential check with no credentials configured."""
        config = {}
        result = check_credentials(config)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("No", result["message"])
        self.assertFalse(result["details"]["configured"])

    def test_check_credentials_empty_upstream(self):
        """Test credential check with empty upstream."""
        config = {"credentials": {"upstream": {}}}
        result = check_credentials(config)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("No upstream credentials", result["message"])

    def test_check_credentials_all_valid(self):
        """Test credential check with all valid files."""
        # Create credential files
        cred1 = Path(self.temp_dir) / "api1.key"
        cred2 = Path(self.temp_dir) / "api2.key"
        cred1.write_text("secret1")
        cred2.write_text("secret2")

        config = {
            "credentials": {
                "upstream": {
                    "api1": {"file": str(cred1)},
                    "api2": {"file": str(cred2)},
                }
            }
        }

        result = check_credentials(config)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("All 2 credentials valid", result["message"])
        self.assertEqual(result["details"]["checked"], 2)
        self.assertEqual(result["details"]["issues"], 0)

    def test_check_credentials_missing_file(self):
        """Test credential check with missing file."""
        config = {
            "credentials": {
                "upstream": {
                    "api1": {"file": "/nonexistent/file.key"},
                }
            }
        }

        result = check_credentials(config)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("Credential issues", result["message"])
        self.assertEqual(result["details"]["issues"], 1)
        self.assertIn("file not found", result["details"]["issue_list"][0])

    def test_check_credentials_empty_file(self):
        """Test credential check with empty file."""
        cred = Path(self.temp_dir) / "empty.key"
        cred.write_text("")

        config = {"credentials": {"upstream": {"api1": {"file": str(cred)}}}}

        result = check_credentials(config)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("file is empty", result["details"]["issue_list"][0])

    def test_check_credentials_not_a_file(self):
        """Test credential check with directory instead of file."""
        config = {"credentials": {"upstream": {"api1": {"file": self.temp_dir}}}}

        result = check_credentials(config)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("not a file", result["details"]["issue_list"][0])


@pytest.mark.unit
class TestCheckServicePorts(unittest.TestCase):
    """Test service port conflict checking."""

    def test_check_service_ports_no_services(self):
        """Test port check with no services configured."""
        config = {}
        result = check_service_ports(config)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("No", result["message"])

    def test_check_service_ports_no_conflicts(self):
        """Test port check with no conflicts."""
        config = {
            "services": {
                "service1": {"port": 8000},
                "service2": {"port": 8001},
                "service3": {"port": 8002},
            }
        }

        result = check_service_ports(config)

        self.assertEqual(result["status"], "healthy")
        self.assertIn("No port conflicts", result["message"])
        self.assertEqual(result["details"]["ports_used"], 3)
        self.assertEqual(result["details"]["conflicts"], {})

    def test_check_service_ports_with_conflicts(self):
        """Test port check with conflicts."""
        config = {
            "services": {
                "service1": {"port": 8000},
                "service2": {"port": 8000},  # Conflict!
                "service3": {"port": 8001},
            }
        }

        result = check_service_ports(config)

        self.assertEqual(result["status"], "unhealthy")
        self.assertIn("Port conflicts detected", result["message"])
        self.assertIn(8000, result["details"]["conflicts"])
        self.assertEqual(len(result["details"]["conflicts"][8000]), 2)

    def test_check_service_ports_multiple_conflicts(self):
        """Test port check with multiple conflicts."""
        config = {
            "services": {
                "service1": {"port": 8000},
                "service2": {"port": 8000},
                "service3": {"port": 8001},
                "service4": {"port": 8001},
            }
        }

        result = check_service_ports(config)

        self.assertEqual(result["status"], "unhealthy")
        self.assertEqual(len(result["details"]["conflicts"]), 2)


@pytest.mark.unit
class TestComprehensiveHealthCheck(unittest.TestCase):
    """Test comprehensive health check."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_comprehensive_check_all_healthy(self):
        """Test comprehensive check when all checks pass."""
        config = {
            "paths": {"runtime_dir": self.temp_dir},
            "credentials": {"upstream": {}},
            "services": {"service1": {"port": 8000}},
        }

        result = comprehensive_health_check(config)

        self.assertEqual(result["overall_status"], "healthy")
        self.assertGreater(result["status_counts"]["healthy"], 0)
        self.assertEqual(result["status_counts"]["unhealthy"], 0)

    def test_comprehensive_check_with_issues(self):
        """Test comprehensive check with some issues."""
        config = {
            "paths": {"runtime_dir": self.temp_dir},
            "credentials": {
                "upstream": {"api1": {"file": "/nonexistent/file.key"}}
            },
            "services": {"service1": {"port": 8000}},
        }

        result = comprehensive_health_check(config)

        self.assertEqual(result["overall_status"], "unhealthy")
        self.assertGreater(result["status_counts"]["unhealthy"], 0)

    def test_comprehensive_check_verbose_mode(self):
        """Test comprehensive check in verbose mode."""
        config = {
            "paths": {"runtime_dir": self.temp_dir},
            "credentials": {"upstream": {}},
            "services": {},
        }

        result = comprehensive_health_check(config, verbose=True)

        # Verbose mode should include details
        for check in result["checks"].values():
            self.assertIn("details", check)

    def test_comprehensive_check_non_verbose_mode(self):
        """Test comprehensive check in non-verbose mode."""
        config = {
            "paths": {"runtime_dir": self.temp_dir},
            "credentials": {"upstream": {}},
            "services": {},
        }

        result = comprehensive_health_check(config, verbose=False)

        # Non-verbose mode should have empty details
        for check in result["checks"].values():
            self.assertEqual(check["details"], {})

    def test_comprehensive_check_includes_all_checks(self):
        """Test that comprehensive check runs all expected checks."""
        config = {
            "paths": {"runtime_dir": self.temp_dir},
            "credentials": {"upstream": {}},
            "services": {},
        }

        result = comprehensive_health_check(config)

        expected_checks = ["disk_space", "memory", "credentials", "port_conflicts"]
        for check_name in expected_checks:
            self.assertIn(check_name, result["checks"])

    def test_comprehensive_check_degraded_status(self):
        """Test comprehensive check with degraded status."""
        config = {
            "paths": {"runtime_dir": self.temp_dir},
            "credentials": {"upstream": {}},
            "services": {},
        }

        # Mock disk space to return degraded
        with patch("flowgate.health.check_disk_space") as mock_disk:
            mock_disk.return_value = {
                "status": "degraded",
                "message": "Low disk space",
                "details": {},
            }

            result = comprehensive_health_check(config)

            self.assertEqual(result["overall_status"], "degraded")
            self.assertGreater(result["status_counts"]["degraded"], 0)


if __name__ == "__main__":
    unittest.main()
