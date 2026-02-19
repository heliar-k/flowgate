import unittest
from unittest import mock

from flowgate.oauth import fetch_auth_url, poll_auth_status

import pytest


@pytest.mark.unit
class OAuthTests(unittest.TestCase):
    def test_fetch_auth_url(self):
        with mock.patch(
            "flowgate.oauth._get_json",
            return_value={"auth_url": "https://example.com/oauth"},
        ):
            auth_url = fetch_auth_url("http://example.local/auth-url", timeout=1)
            self.assertEqual(auth_url, "https://example.com/oauth")

    def test_poll_auth_status_success(self):
        responses = [
            {"status": "pending"},
            {"status": "success"},
        ]

        with mock.patch("flowgate.oauth._get_json", side_effect=responses):
            status = poll_auth_status(
                "http://example.local/status",
                timeout_seconds=3,
                poll_interval_seconds=0.01,
            )
            self.assertEqual(status, "success")

    def test_poll_auth_status_tolerates_transient_network_error(self):
        responses = [
            TimeoutError("temporary timeout"),
            {"status": "pending"},
            {"status": "success"},
        ]

        with mock.patch("flowgate.oauth._get_json", side_effect=responses):
            status = poll_auth_status(
                "http://example.local/status",
                timeout_seconds=3,
                poll_interval_seconds=0.01,
            )
            self.assertEqual(status, "success")


if __name__ == "__main__":
    unittest.main()
