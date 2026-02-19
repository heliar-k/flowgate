"""Error path tests for authentication module.

This module tests error handling in oauth.py and headless_import.py,
ensuring proper exception handling for OAuth flows and headless imports.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from flowgate.oauth import fetch_auth_url, poll_auth_status
from flowgate.headless_import import import_codex_headless_auth

import pytest

@pytest.mark.unit
class TestOAuthErrorHandling(unittest.TestCase):
    """Test OAuth error handling."""

    def test_fetch_auth_url_non_json_response(self):
        """Test ValueError when auth-url endpoint returns non-JSON."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
            with self.assertRaises(Exception):  # json.JSONDecodeError
                fetch_auth_url("http://localhost:9000/auth-url")

    def test_fetch_auth_url_non_dict_response(self):
        """Test ValueError when auth-url endpoint returns non-dict JSON."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'["not", "a", "dict"]'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("OAuth endpoint must return a JSON object", str(ctx.exception))

    def test_fetch_auth_url_missing_url_field(self):
        """Test ValueError when auth-url endpoint missing all expected URL fields."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"other_field": "value"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("did not return auth_url/url/login_url", str(ctx.exception))

    def test_fetch_auth_url_empty_url_field(self):
        """Test ValueError when auth_url field is empty string."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"auth_url": ""}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("did not return auth_url/url/login_url", str(ctx.exception))

    def test_fetch_auth_url_whitespace_only_url(self):
        """Test ValueError when auth_url field is whitespace only."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"auth_url": "   "}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                fetch_auth_url("http://localhost:9000/auth-url")
            self.assertIn("did not return auth_url/url/login_url", str(ctx.exception))

    def test_fetch_auth_url_network_error(self):
        """Test exception when auth-url endpoint is unreachable."""
        with mock.patch(
            "flowgate.oauth.urlopen", side_effect=URLError("Connection refused")
        ):
            with self.assertRaises(URLError):
                fetch_auth_url("http://localhost:9000/auth-url", timeout=1)

    def test_fetch_auth_url_timeout(self):
        """Test exception when auth-url endpoint times out."""
        with mock.patch("flowgate.oauth.urlopen", side_effect=TimeoutError("Timeout")):
            with self.assertRaises(TimeoutError):
                fetch_auth_url("http://localhost:9000/auth-url", timeout=1)

    def test_poll_auth_status_timeout(self):
        """Test TimeoutError when polling exceeds timeout."""
        mock_response = mock.Mock()
        mock_response.read.return_value = b'{"status": "pending"}'
        mock_response.__enter__ = mock.Mock(return_value=mock_response)
        mock_response.__exit__ = mock.Mock(return_value=False)

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
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

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
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

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
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

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
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

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
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

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
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
            "flowgate.oauth.urlopen", side_effect=URLError("Connection refused")
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

        with mock.patch("flowgate.oauth.urlopen", return_value=mock_response):
            with self.assertRaises(ValueError) as ctx:
                poll_auth_status(
                    "http://localhost:9000/status",
                    timeout_seconds=1,
                    poll_interval_seconds=0.1,
                )
            self.assertIn("OAuth endpoint must return a JSON object", str(ctx.exception))

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

        with mock.patch("flowgate.oauth.urlopen", side_effect=mock_urlopen):
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
        self.assertIn("Headless auth file missing tokens.access_token", str(ctx.exception))

    def test_import_empty_access_token(self):
        """Test ValueError when access_token is empty string."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(
            '{"tokens": {"access_token": "", "refresh_token": "refresh123"}}'
        )
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn("Headless auth file missing tokens.access_token", str(ctx.exception))

    def test_import_whitespace_only_access_token(self):
        """Test ValueError when access_token is whitespace only."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(
            '{"tokens": {"access_token": "   ", "refresh_token": "refresh123"}}'
        )
        tmp.flush()
        tmp.close()
        source_path = Path(tmp.name)

        dest_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError) as ctx:
            import_codex_headless_auth(source_path, dest_dir)
        self.assertIn("Headless auth file missing tokens.access_token", str(ctx.exception))

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
        tmp.write(
            '{"tokens": {"access_token": "access123", "refresh_token": ""}}'
        )
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
        tmp.write(
            '{"tokens": {"access_token": "access123", "refresh_token": "   "}}'
        )
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


if __name__ == "__main__":
    unittest.main()
