"""Integration tests: OAuth polling flow with a mock HTTP server.

Uses ``http.server`` to spin up a temporary HTTP server that simulates
the provider auth-URL and status endpoints.  No network access to real
OAuth providers is required.

Run with:
    pytest tests/integration/test_oauth_flow.py -v -m integration
"""
from __future__ import annotations

import json
import queue
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.error import URLError

import pytest

from flowgate.oauth import fetch_auth_url, poll_auth_status

from .base import IntegrationTestBase


# ---------------------------------------------------------------------------
# Mock OAuth server
# ---------------------------------------------------------------------------


class _MockOAuthHandler(BaseHTTPRequestHandler):
    """Request handler that serves pre-configured responses from a queue."""

    # Silence the default access-log output during tests.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D102
        pass

    def do_GET(self) -> None:  # noqa: N802
        server: MockOAuthServer = self.server  # type: ignore[assignment]
        try:
            status_code, body = server.response_queue.get_nowait()
        except queue.Empty:
            # No more responses queued – return 503 so the poller keeps going
            status_code, body = 503, {"status": "pending"}

        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class MockOAuthServer:
    """A lightweight mock OAuth server backed by an in-memory response queue.

    Usage::

        with MockOAuthServer() as mock:
            mock.enqueue(200, {"auth_url": "https://example.com/login"})
            mock.enqueue(200, {"status": "pending"})
            mock.enqueue(200, {"status": "success"})
            auth_url = fetch_auth_url(mock.auth_url_endpoint)
            result  = poll_auth_status(mock.status_endpoint, timeout_seconds=5)
    """

    def __init__(self) -> None:
        self.response_queue: queue.Queue[tuple[int, dict[str, Any]]] = queue.Queue()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.host = "127.0.0.1"
        self.port: int = 0

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "MockOAuthServer":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the mock server on a randomly assigned free port."""
        self._server = HTTPServer((self.host, 0), _MockOAuthHandler)
        self._server.response_queue = self.response_queue  # type: ignore[attr-defined]
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Shut the server down cleanly."""
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def enqueue(self, status_code: int, body: dict[str, Any]) -> None:
        """Queue a single HTTP response to be served to the next request."""
        self.response_queue.put((status_code, body))

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def auth_url_endpoint(self) -> str:
        return f"{self.base_url}/auth-url"

    @property
    def status_endpoint(self) -> str:
        return f"{self.base_url}/status"


# ---------------------------------------------------------------------------
# Tests: fetch_auth_url
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFetchAuthUrl(IntegrationTestBase):
    """Tests for ``flowgate.oauth.fetch_auth_url``."""

    def test_returns_auth_url_from_auth_url_key(self) -> None:
        """fetch_auth_url extracts value from the 'auth_url' key."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"auth_url": "https://example.com/login?code=abc"})
            result = fetch_auth_url(mock.auth_url_endpoint, timeout=5.0)
        self.assertEqual(result, "https://example.com/login?code=abc")

    def test_returns_auth_url_from_url_key(self) -> None:
        """fetch_auth_url also accepts the 'url' key."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"url": "https://example.com/device"})
            result = fetch_auth_url(mock.auth_url_endpoint, timeout=5.0)
        self.assertEqual(result, "https://example.com/device")

    def test_returns_auth_url_from_login_url_key(self) -> None:
        """fetch_auth_url also accepts the 'login_url' key."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"login_url": "https://example.com/login"})
            result = fetch_auth_url(mock.auth_url_endpoint, timeout=5.0)
        self.assertEqual(result, "https://example.com/login")

    def test_raises_if_no_auth_url_in_response(self) -> None:
        """fetch_auth_url raises ValueError when no URL key is present."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"error": "no_url_here"})
            with self.assertRaises(ValueError):
                fetch_auth_url(mock.auth_url_endpoint, timeout=5.0)

    def test_raises_on_connection_error(self) -> None:
        """fetch_auth_url raises when the endpoint is unreachable."""
        # Port 1 is privileged and should always be refused.
        with self.assertRaises((URLError, OSError)):
            fetch_auth_url("http://127.0.0.1:1/auth-url", timeout=1.0)


# ---------------------------------------------------------------------------
# Tests: poll_auth_status – success path
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPollAuthStatusSuccess(IntegrationTestBase):
    """Tests for the success paths of ``flowgate.oauth.poll_auth_status``."""

    def test_immediate_success_status(self) -> None:
        """poll_auth_status returns 'success' when the first poll succeeds."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"status": "success"})
            result = poll_auth_status(
                mock.status_endpoint,
                timeout_seconds=10,
                poll_interval_seconds=0.1,
            )
        self.assertEqual(result, "success")

    def test_success_after_pending_states(self) -> None:
        """poll_auth_status keeps polling through 'pending' until 'success'."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"status": "pending"})
            mock.enqueue(200, {"status": "pending"})
            mock.enqueue(200, {"status": "success"})
            result = poll_auth_status(
                mock.status_endpoint,
                timeout_seconds=10,
                poll_interval_seconds=0.05,
            )
        self.assertEqual(result, "success")

    def test_completed_state_is_accepted(self) -> None:
        """The 'completed' status value is treated as success."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"status": "completed"})
            result = poll_auth_status(
                mock.status_endpoint,
                timeout_seconds=10,
                poll_interval_seconds=0.1,
            )
        self.assertEqual(result, "completed")

    def test_authorized_state_is_accepted(self) -> None:
        """The 'authorized' status value is treated as success."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"status": "authorized"})
            result = poll_auth_status(
                mock.status_endpoint,
                timeout_seconds=10,
                poll_interval_seconds=0.1,
            )
        self.assertEqual(result, "authorized")


# ---------------------------------------------------------------------------
# Tests: poll_auth_status – failure paths
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPollAuthStatusFailure(IntegrationTestBase):
    """Tests for failure / error paths of ``flowgate.oauth.poll_auth_status``."""

    def test_failed_status_raises_runtime_error(self) -> None:
        """poll_auth_status raises RuntimeError when status is 'failed'."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"status": "failed"})
            with self.assertRaises(RuntimeError) as ctx:
                poll_auth_status(
                    mock.status_endpoint,
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )
        self.assertIn("failed", str(ctx.exception))

    def test_denied_status_raises_runtime_error(self) -> None:
        """poll_auth_status raises RuntimeError when status is 'denied'."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"status": "denied"})
            with self.assertRaises(RuntimeError):
                poll_auth_status(
                    mock.status_endpoint,
                    timeout_seconds=5,
                    poll_interval_seconds=0.1,
                )

    def test_timeout_raises_timeout_error(self) -> None:
        """poll_auth_status raises TimeoutError when deadline is exceeded."""
        with MockOAuthServer() as mock:
            # Always return 'pending' – never reaches success.
            for _ in range(50):
                mock.enqueue(200, {"status": "pending"})
            with self.assertRaises(TimeoutError):
                poll_auth_status(
                    mock.status_endpoint,
                    timeout_seconds=0.3,
                    poll_interval_seconds=0.05,
                )

    def test_network_errors_are_retried_until_timeout(self) -> None:
        """Network errors during polling are retried; TimeoutError raised if deadline hit."""
        # Do not enqueue any responses – server returns 503 every time and
        # the parsed body {"status": "pending"} keeps polling alive until timeout.
        with MockOAuthServer() as mock:
            with self.assertRaises(TimeoutError):
                poll_auth_status(
                    mock.status_endpoint,
                    timeout_seconds=0.3,
                    poll_interval_seconds=0.05,
                )


# ---------------------------------------------------------------------------
# Tests: full OAuth flow end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOAuthFlowEndToEnd(IntegrationTestBase):
    """End-to-end: fetch auth URL then poll until completion."""

    def test_full_oauth_flow_success(self) -> None:
        """Simulates a complete device-auth flow: get URL then poll to success."""
        with MockOAuthServer() as mock:
            # Phase 1: fetch the auth URL
            mock.enqueue(200, {"auth_url": "https://example.com/activate?code=XYZ"})
            auth_url = fetch_auth_url(mock.auth_url_endpoint, timeout=5.0)
            self.assertIn("XYZ", auth_url)

            # Phase 2: poll for completion
            mock.enqueue(200, {"status": "pending"})
            mock.enqueue(200, {"status": "success"})
            result = poll_auth_status(
                mock.status_endpoint,
                timeout_seconds=10,
                poll_interval_seconds=0.05,
            )
        self.assertEqual(result, "success")

    def test_full_oauth_flow_user_denies(self) -> None:
        """Simulates a user denying the device-auth request."""
        with MockOAuthServer() as mock:
            mock.enqueue(200, {"auth_url": "https://example.com/activate"})
            fetch_auth_url(mock.auth_url_endpoint, timeout=5.0)

            mock.enqueue(200, {"status": "pending"})
            mock.enqueue(200, {"status": "denied"})
            with self.assertRaises(RuntimeError):
                poll_auth_status(
                    mock.status_endpoint,
                    timeout_seconds=10,
                    poll_interval_seconds=0.05,
                )


if __name__ == "__main__":
    unittest.main()
