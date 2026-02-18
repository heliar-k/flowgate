from __future__ import annotations

import unittest

from flowgate.integration import build_integration_specs


class IntegrationSpecTests(unittest.TestCase):
    def test_build_integration_specs_from_litellm_service(self):
        cfg = {
            "services": {"litellm": {"host": "127.0.0.1", "port": 4000}},
            "integration": {
                "default_model": "router-default",
                "fast_model": "router-cheap",
            },
        }

        specs = build_integration_specs(cfg)

        self.assertEqual(specs["codex"]["base_url"], "http://127.0.0.1:4000/v1")
        self.assertEqual(specs["codex"]["model"], "router-default")
        self.assertEqual(specs["claude_code"]["base_url"], "http://127.0.0.1:4000")
        self.assertEqual(
            specs["claude_code"]["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"],
            "router-default",
        )
        self.assertEqual(
            specs["claude_code"]["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"],
            "router-cheap",
        )

    def test_build_integration_specs_defaults_fast_model_to_default_model(self):
        cfg = {
            "services": {"litellm": {"port": 4000}},
            "integration": {"default_model": "router-default"},
        }

        specs = build_integration_specs(cfg)

        self.assertEqual(specs["codex"]["base_url"], "http://127.0.0.1:4000/v1")
        self.assertEqual(
            specs["claude_code"]["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"],
            "router-default",
        )


if __name__ == "__main__":
    unittest.main()
