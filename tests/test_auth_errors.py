"""Error path tests for authentication module.

This module tests error handling in oauth.py and headless_import.py,
ensuring proper exception handling for OAuth flows and headless imports.
"""

import base64
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

import pytest

from flowgate.core.auth import (
    fetch_auth_url,
    import_codex_headless_auth,
    import_kiro_headless_auth,
    poll_auth_status,
)


@pytest.mark.unit
class TestOAuthErrorHandling(unittest.TestCase):
    """Test OAuth error handling."""

    def test_fetch_auth_url_non_json_response(self):
        """Test ValueError when auth-url endpoint returns non-JSON."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(Exception):  # json.JSONDecodeError
                fetch_auth_url("http://localhost:9000/auth-url")

    def test_fetch_auth_url_non_dict_response(self):
        """Test ValueError when auth-url endpoint returns non-dict JSON."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'["not", "a", "dict"]'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn(
                "OAuth endpoint must return a JSON object", str(ctx.exception)
            )

    def test_fetch_auth_url_missing_url_field(self):
        """Test ValueError when auth-url endpoint missing all expected URL fields."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"other_field": "value"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("did not return auth_url/url/login_url", str(ctx.exception))

    def test_fetch_auth_url_empty_url_field(self):
        """Test ValueError when auth_url field is empty string."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"auth_url": ""}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("did not return auth_url/url/login_url", str(ctx.exception))

    def test_fetch_auth_url_whitespace_only_url(self):
        """Test ValueError when auth_url field is whitespace only."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"auth_url": "   "}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("did not return auth_url/url/login_url", str(ctx.exception))

    def test_fetch_auth_url_network_error(self):
        """Test exception when auth-url endpoint is unreachable."""
        with mock.patch(
            "flowgate.core.auth.urlopen", side_effect=URLError("Connection refused")
        ):
            with self.assertRaises(URLError):
                fetch_auth_url("http://localhost:9000/auth-url", timeout=1)

    def test_fetch_auth_url_timeout(self):
        """Test exception when auth-url endpoint times out."""
        with mock.patch(
            "flowgate.core.auth.urlopen", side_effect=TimeoutError("Timeout")
        ):
            with self.assertRaises(TimeoutError):
                fetch_auth_url("http://localhost:9000/auth-url", timeout=1)

    def test_poll_auth_status_timeout(self):
        """Test TimeoutError when polling exceeds timeout."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "pending"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(TimeoutError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=0.5,
                    poll_interval_seconds=0.1,
                )
            self.assertIn("OAuth login timed out", str(ctx.exception))
            self.assertIn("last status=pending", str(ctx.exception))

    def test_poll_auth_status_failed_state(self):
        """Test RuntimeError when status endpoint returns failed state."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "failed"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )
            self.assertIn("OAuth login failed with status: failed", str(ctx.exception))

    def test_poll_auth_status_error_state(self):
        """Test RuntimeError when status endpoint returns error state."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "error"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )
            self.assertIn("OAuth login failed with status: error", str(ctx.exception))

    def test_poll_auth_status_denied_state(self):
        """Test RuntimeError when status endpoint returns denied state."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "denied"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )
            self.assertIn("OAuth login failed with status: denied", str(ctx.exception))

    def test_poll_auth_status_expired_state(self):
        """Test RuntimeError when status endpoint returns expired state."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "expired"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )
            self.assertIn("OAuth login failed with status: expired", str(ctx.exception))

    def test_poll_auth_status_cancelled_state(self):
        """Test RuntimeError when status endpoint returns cancelled state."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "cancelled"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )
            self.assertIn(
                "OAuth login failed with status: cancelled", str(ctx.exception)
            )

    def test_poll_auth_status_network_error_with_timeout(self):
        """Test TimeoutError includes last network error when polling times out."""
        with mock.patch(
            "flowgate.core.auth.urlopen", side_effect=URLError("Connection refused")
        ):
            with self.assertRaises(TimeoutError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=0.5,
                    poll_interval_seconds=0.1,
                )
            exception_str = str(ctx.exception)
            self.assertIn("OAuth login timed out", exception_str)
            self.assertIn("last error", exception_str)

    def test_poll_auth_status_non_dict_response(self):
        """Test ValueError when status endpoint returns non-dict JSON."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'["not", "a", "dict"]'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.core.auth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=1,
                    poll_interval_seconds=0.1,
                )
            self.assertIn(
                "OAuth endpoint must return a JSON object", str(ctx.exception)
            )

    def test_poll_auth_status_success_after_pending(self):
        """Test successful auth after initial pending status."""
        responses = [
            b'{"status": "pending"}',
            b'{"status": "pending"}',
            b'{"status": "success"}',
        ]
        response_iter = iter(responses)

        def mock_urlopen(*args, **kwargs):
            mock_response = mock.Mock()
            mock_response.read.return_value = next(response_iter)
            mock_response.__enter__ = mock.Mock(return_value=mock_response)
            mock_response.__exit__ = mock.Mock(return_value=False)
            return mock_response

        with mock.patch("flowgate.core.auth.urlopen", side_effect=mock_urlopen):
            status = poll_auth_status(
                "http://localhost:9000/status",
                timeout_seconds=5,
                poll_interval_seconds=0.1,
            )

            self.assertEqual(status, "success")


@pytest.mark.unit
class TestHeadlessImportErrorHandling(unittest.TestCase):
    """Test headless import error handling."""

    def test_import_source_file_not_found(self):
        """Test FileNotFoundError when source file does not exist."""
        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(FileNotFoundError) as ctx:
            import_codex_headless_auth("/non/existent/file.json", dest_dir)
        self.assertIn("Source auth file not found", str(ctx.exception))

    def test_import_invalid_json(self):
        """Test ValueError when source file contains invalid JSON."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write("{invalid json")
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn("Invalid JSON file", str(ctx.exception))

    def test_import_json_not_dict(self):
        """Test ValueError when source JSON is not a dict."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('["not", "a", "dict"]')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn("Headless auth file must be a JSON object", str(ctx.exception))

    def test_import_missing_tokens_object(self):
        """Test ValueError when tokens object is missing."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"other_field": "value"}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn("Headless auth file missing tokens object", str(ctx.exception))

    def test_import_tokens_not_dict(self):
        """Test ValueError when tokens is not a dict."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": "not-a-dict"}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn("Headless auth file missing tokens object", str(ctx.exception))

    def test_import_missing_access_token(self):
        """Test ValueError when access_token is missing."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": {"refresh_token": "refresh123"}}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn(
            "Headless auth file missing tokens.access_token", str(ctx.exception)
        )

    def test_import_empty_access_token(self):
        """Test ValueError when access_token is empty string."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": {"access_token": "", "refresh_token": "refresh123"}}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn(
            "Headless auth file missing tokens.access_token", str(ctx.exception)
        )

    def test_import_whitespace_only_access_token(self):
        """Test ValueError when access_token is whitespace only."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": {"access_token": "   ", "refresh_token": "refresh123"}}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn(
            "Headless auth file missing tokens.access_token", str(ctx.exception)
        )

    def test_import_missing_refresh_token(self):
        """Test ValueError when refresh_token is missing."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": {"access_token": "access123"}}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn(
            "Headless auth file missing tokens.refresh_token", str(ctx.exception)
        )

    def test_import_empty_refresh_token(self):
        """Test ValueError when refresh_token is empty string."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": {"access_token": "access123", "refresh_token": ""}}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn(
            "Headless auth file missing tokens.refresh_token", str(ctx.exception)
        )

    def test_import_whitespace_only_refresh_token(self):
        """Test ValueError when refresh_token is whitespace only."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write('{"tokens": {"access_token": "access123", "refresh_token": "   "}}')
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn(
            "Headless auth file missing tokens.refresh_token", str(ctx.exception)
        )

    def test_import_successful_with_all_tokens(self):
        """Test successful import with all token fields present."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(
            json.dumps(
                {
                    "tokens": {
                        "access_token": "access123",
                        "refresh_token": "refresh123",
                        "id_token": "id123",
                        "account_id": "account123",
                    }
                }
            )
        )
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        output_path = import_codex_headless_auth(source_path, dest_dir)

        self.assertTrue(output_path.exists())
        output_data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(output_data["access_token"], "access123")
        self.assertEqual(output_data["refresh_token"], "refresh123")
        self.assertEqual(output_data["id_token"], "id123")
        self.assertEqual(output_data["account_id"], "account123")

    def test_import_successful_with_minimal_tokens(self):
        """Test successful import with only required token fields."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(
            json.dumps(
                {
                    "tokens": {
                        "access_token": "access123",
                        "refresh_token": "refresh123",
                    }
                }
            )
        )
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        output_path = import_codex_headless_auth(source_path, dest_dir)

        self.assertTrue(output_path.exists())
        output_data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(output_data["access_token"], "access123")
        self.assertEqual(output_data["refresh_token"], "refresh123")
        self.assertEqual(output_data["id_token"], "")
        self.assertEqual(output_data["account_id"], "")


@pytest.mark.unit
class TestKiroHeadlessImport(unittest.TestCase):
    """Test Kiro headless import scanning and normalization."""

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.dest_dir = Path(tempfile.mkdtemp())

    def _jwt_with_email(self, email: str) -> str:
        payload = base64.urlsafe_b64encode(
            json.dumps({"email": email}).encode("utf-8")
        ).decode("ascii")
        payload = payload.rstrip("=")
        return f"header.{payload}.signature"

    def _write_kiro_token(
        self,
        path: Path,
        *,
        access_token: str | None = None,
        refresh_token: str = "refresh-token",
        provider: str = "Google",
        email: str = "",
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "accessToken": access_token or self._jwt_with_email("kiro@example.com"),
            "refreshToken": refresh_token,
            "expiresAt": "2030-01-01T00:00:00Z",
            "profileArn": "arn:aws:codewhisperer:us-east-1:123456789012:profile/test-profile",
            "authMethod": "social",
            "provider": provider,
            "clientId": "client-id",
            "clientSecret": "client-secret",
            "clientIdHash": "client-hash",
            "email": email,
            "startUrl": "https://example.awsapps.com/start",
            "region": "us-east-1",
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_import_kiro_source_file_not_found(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            import_kiro_headless_auth("/non/existent/kiro.json", self.dest_dir)
        self.assertIn("Source auth file not found", str(ctx.exception))

    def test_import_kiro_scans_primary_known_location(self):
        source = self._write_kiro_token(self.home / ".kiro" / "kiro-auth-token.json")

        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            output_path = import_kiro_headless_auth("", self.dest_dir)

        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "kiro-google-kiro-example-com.json")
        output_data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(output_data["access_token"], json.loads(source.read_text())["accessToken"])
        self.assertEqual(output_data["refresh_token"], "refresh-token")
        self.assertEqual(output_data["provider"], "Google")
        self.assertEqual(output_data["email"], "kiro@example.com")

    def test_import_kiro_scans_fallback_location(self):
        self._write_kiro_token(self.home / ".aws" / "sso" / "cache" / "kiro-auth-token.json")

        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            output_path = import_kiro_headless_auth("", self.dest_dir)

        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "kiro-google-kiro-example-com.json")

    def test_import_kiro_uses_explicit_source_before_scan(self):
        explicit = self._write_kiro_token(
            self.home / "explicit.json",
            provider="Enterprise",
            email="explicit@example.com",
        )
        self._write_kiro_token(self.home / ".kiro" / "kiro-auth-token.json")

        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            output_path = import_kiro_headless_auth(str(explicit), self.dest_dir)

        self.assertEqual(output_path.name, "kiro-enterprise-explicit-example-com.json")

    def test_import_kiro_reports_scanned_locations_when_not_found(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            with self.assertRaises(FileNotFoundError) as ctx:
                import_kiro_headless_auth("", self.dest_dir)

        message = str(ctx.exception)
        self.assertIn("Kiro IDE token file not found", message)
        self.assertIn(str((self.home / ".kiro" / "kiro-auth-token.json").resolve()), message)
        self.assertIn(
            str((self.home / ".aws" / "sso" / "cache" / "kiro-auth-token.json").resolve()),
            message,
        )

    def test_import_kiro_missing_access_token(self):
        source = self.home / ".kiro" / "kiro-auth-token.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps({"refreshToken": "refresh-token", "expiresAt": "2030-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError) as ctx:
            import_kiro_headless_auth(str(source), self.dest_dir)
        self.assertIn("Headless auth file missing accessToken", str(ctx.exception))

    def test_import_kiro_missing_refresh_token(self):
        source = self.home / ".kiro" / "kiro-auth-token.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            json.dumps(
                {
                    "accessToken": self._jwt_with_email("kiro@example.com"),
                    "expiresAt": "2030-01-01T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(ValueError) as ctx:
            import_kiro_headless_auth(str(source), self.dest_dir)
        self.assertIn("Headless auth file missing refreshToken", str(ctx.exception))

    def test_import_kiro_extracts_email_from_jwt(self):
        source = self._write_kiro_token(
            self.home / ".kiro" / "kiro-auth-token.json",
            email="",
            access_token=self._jwt_with_email("derived@example.com"),
        )

        output_path = import_kiro_headless_auth(str(source), self.dest_dir)

        output_data = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(output_data["email"], "derived@example.com")
        self.assertEqual(output_path.name, "kiro-google-derived-example-com.json")

    def test_import_kiro_output_permissions(self):
        source = self._write_kiro_token(self.home / ".kiro" / "kiro-auth-token.json")

        output_path = import_kiro_headless_auth(str(source), self.dest_dir)

        self.assertEqual(output_path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
