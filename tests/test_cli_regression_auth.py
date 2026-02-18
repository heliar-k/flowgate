"""CLI regression tests - auth command group

Verifies that auth commands maintain consistent exit codes and output formats.
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
        },
        "auth": {
            "providers": {
                "codex": {
                    "auth_url_endpoint": "http://example.local/codex/auth-url",
                    "status_endpoint": "http://example.local/codex/status",
                },
                "copilot": {
                    "auth_url_endpoint": "http://example.local/copilot/auth-url",
                    "status_endpoint": "http://example.local/copilot/status",
                },
            }
        },
        "secret_files": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestAuthCommandExitCodes(unittest.TestCase):
    """Regression tests for auth command exit codes"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_minimal_config(self.cfg)

    def test_auth_list_success_exit_code(self) -> None:
        """auth list returns exit code 0 on success"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(
            result,
            0,
            f"Expected exit code 0, got {result}\nstdout: {out.getvalue()}",
        )

    def test_auth_list_missing_config_exit_code(self) -> None:
        """auth list returns non-zero exit code when config file is missing"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", "/nonexistent/config.yaml", "auth", "list"],
            stdout=out,
            stderr=err,
        )
        self.assertNotEqual(result, 0, "Expected non-zero exit code")
        error_output = err.getvalue() + out.getvalue()
        self.assertTrue(
            "does not exist" in error_output.lower() or "not found" in error_output.lower(),
            f"Expected config file error message, got: {error_output}",
        )

    def test_auth_status_success_exit_code(self) -> None:
        """auth status returns exit code 0 on success (even when no auth exists)"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "status"], stdout=out)
        self.assertEqual(result, 0, f"stdout: {out.getvalue()}")

    def test_auth_login_invalid_provider_exit_code(self) -> None:
        """auth login returns exit code 2 when provider is invalid"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", str(self.cfg), "auth", "login", "nonexistent-provider", "--timeout", "1"],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 2, "Expected exit code 2 (config error)")
        error_output = err.getvalue() + out.getvalue()
        self.assertTrue(
            "not configured" in error_output.lower() or "available=" in error_output,
            f"Expected provider error message, got: {error_output}",
        )

    def test_auth_login_timeout_exit_code(self) -> None:
        """auth login returns exit code 1 on timeout"""
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch("flowgate.cli.fetch_auth_url", return_value="https://example.com/login"),
            mock.patch(
                "flowgate.cli.poll_auth_status",
                side_effect=TimeoutError("OAuth login timed out"),
            ),
        ):
            result = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex", "--timeout", "1"],
                stdout=out,
                stderr=err,
            )
        self.assertEqual(result, 1, "Expected exit code 1 (runtime error)")
        self.assertIn("OAuth login failed", err.getvalue())

    def test_auth_import_headless_missing_source_exit_code(self) -> None:
        """auth import-headless returns exit code 1 when source file is missing"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            [
                "--config",
                str(self.cfg),
                "auth",
                "import-headless",
                "codex",
                "--source",
                "/nonexistent/auth.json",
            ],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 1, "Expected exit code 1 (file not found)")
        error_output = err.getvalue() + out.getvalue()
        self.assertTrue(
            "does not exist" in error_output.lower() or "not found" in error_output.lower(),
            f"Expected file not found error, got: {error_output}",
        )

    def test_auth_import_headless_invalid_json_exit_code(self) -> None:
        """auth import-headless returns exit code 1 when JSON file is invalid"""
        invalid_json_path = self.root / "invalid.json"
        invalid_json_path.write_text("invalid json{", encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            [
                "--config",
                str(self.cfg),
                "auth",
                "import-headless",
                "codex",
                "--source",
                str(invalid_json_path),
            ],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 1, "Expected exit code 1 (JSON parse error)")
        error_output = err.getvalue()
        self.assertTrue(error_output, "Expected error output")
        self.assertTrue(
            "json" in error_output.lower() or "parse" in error_output.lower(),
            f"Expected JSON parsing error message, got: {error_output}",
        )

    def test_auth_import_headless_unsupported_provider_exit_code(self) -> None:
        """auth import-headless returns exit code 2 when provider is unsupported"""
        valid_json_path = self.root / "valid.json"
        valid_json_path.write_text("{}", encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            [
                "--config",
                str(self.cfg),
                "auth",
                "import-headless",
                "copilot",  # copilot does not support headless import
                "--source",
                str(valid_json_path),
            ],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 2, "Expected exit code 2 (unsupported feature)")
        self.assertIn("not supported", err.getvalue())


class TestAuthCommandOutput(unittest.TestCase):
    """Regression tests for auth command output formats"""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_minimal_config(self.cfg)

    def test_auth_list_output_format(self) -> None:
        """auth list output includes providers and capability information"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(result, 0)

        output = out.getvalue()
        # Verify output contains configured providers
        self.assertIn("provider=codex", output, "Output should include codex provider")
        self.assertIn("provider=copilot", output, "Output should include copilot provider")

        # Verify output contains capability information
        self.assertIn("oauth_login=", output, "Output should include oauth_login capability")
        self.assertIn("headless_import=", output, "Output should include headless_import capability")

        # Verify summary line
        self.assertIn("oauth_providers=", output, "Output should include oauth_providers summary")
        self.assertIn("headless_import_providers=", output, "Output should include headless_import_providers summary")

    def test_auth_status_output_format(self) -> None:
        """auth status output includes default_auth_dir and provider information"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "status"], stdout=out)
        self.assertEqual(result, 0)

        output = out.getvalue()
        # Verify output contains key fields
        self.assertIn("default_auth_dir=", output, "Output should include default_auth_dir")
        self.assertIn("secret_permission_issues=", output, "Output should include secret_permission_issues")
        self.assertIn("provider=codex", output, "Output should include codex provider")
        self.assertIn("method=", output, "Output should include authentication method")

    def test_auth_login_success_output_format(self) -> None:
        """auth login success output includes login_url and oauth_status"""
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.fetch_auth_url", return_value="https://example.com/login"),
            mock.patch("flowgate.cli.poll_auth_status", return_value="success"),
        ):
            result = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex", "--timeout", "5"],
                stdout=out,
            )
        self.assertEqual(result, 0)

        output = out.getvalue()
        self.assertIn("login_url=", output, "Output should include login_url")
        self.assertIn("https://example.com/login", output, "Output should include actual login URL")
        self.assertIn("oauth_status=", output, "Output should include oauth_status")

    def test_auth_import_headless_success_output_format(self) -> None:
        """auth import-headless success output includes saved_auth path"""
        valid_auth_path = self.root / "valid_auth.json"
        valid_auth_path.write_text(
            json.dumps({"token": "test-token", "expires_at": 9999999999}),
            encoding="utf-8",
        )

        out = io.StringIO()
        handler = mock.Mock(return_value=Path("/tmp/auths/codex-headless-import.json"))
        with mock.patch("flowgate.cli.get_headless_import_handler", return_value=handler):
            result = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "auth",
                    "import-headless",
                    "codex",
                    "--source",
                    str(valid_auth_path),
                ],
                stdout=out,
            )
        self.assertEqual(result, 0)

        output = out.getvalue()
        self.assertIn("saved_auth=", output, "Output should include saved_auth")
        self.assertIn("/tmp/auths/codex-headless-import.json", output, "Output should include actual save path")

    def test_auth_login_error_output_contains_hint(self) -> None:
        """auth login error output includes debugging hint"""
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch("flowgate.cli.fetch_auth_url", return_value="https://example.com/login"),
            mock.patch(
                "flowgate.cli.poll_auth_status",
                side_effect=TimeoutError("OAuth login timed out; last status=pending"),
            ),
        ):
            result = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex", "--timeout", "1"],
                stdout=out,
                stderr=err,
            )
        self.assertNotEqual(result, 0)

        error_output = err.getvalue()
        self.assertIn("hint=", error_output, "Error output should include debugging hint")
        self.assertIn("auth status", error_output, "Hint should suggest running auth status")

    def test_auth_list_empty_providers_output(self) -> None:
        """auth list output format when no providers are configured"""
        # Create config without auth providers
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["auth"]["providers"] = {}
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(result, 0)

        output = out.getvalue()
        self.assertIn("oauth_providers=none", output, "Should output 'none' when no providers configured")
        self.assertIn("headless_import_providers=none", output, "Should output 'none' when no headless providers configured")


if __name__ == "__main__":
    unittest.main()
