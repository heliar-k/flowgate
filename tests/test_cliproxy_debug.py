from __future__ import annotations

import unittest

from flowgate.cliproxy_debug import management_api_url_from_auth, management_page_url


class CliproxyDebugTests(unittest.TestCase):
    def test_management_page_url_uses_root_path(self) -> None:
        self.assertEqual(
            management_page_url("127.0.0.1", 8317),
            "http://127.0.0.1:8317/",
        )

    def test_management_api_url_follows_auth_endpoint_base(self) -> None:
        config = {
            "auth": {
                "providers": {
                    "codex": {
                        "auth_url_endpoint": "http://127.0.0.1:8317/v0/management/oauth/codex/auth-url"
                    }
                }
            }
        }
        self.assertEqual(
            management_api_url_from_auth(config, "127.0.0.1", 8317),
            "http://127.0.0.1:8317/v0/management",
        )
