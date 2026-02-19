from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from flowgate.client_apply import apply_claude_code_settings, apply_codex_config

import pytest


@pytest.mark.unit
class ClientApplyTests(unittest.TestCase):
    def test_apply_claude_creates_backup_and_merges_managed_env_keys(self):
        root = Path(tempfile.mkdtemp())
        target = root / "settings.json"
        target.write_text(
            json.dumps(
                {
                    "env": {
                        "ANTHROPIC_AUTH_TOKEN": "old-token",
                        "UNCHANGED_KEY": "keep",
                    },
                    "allowedTools": ["Bash"],
                }
            ),
            encoding="utf-8",
        )

        spec = {
            "base_url": "http://127.0.0.1:4000",
            "env": {
                "ANTHROPIC_MODEL": "router-default",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "router-default",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "router-default",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "router-cheap",
            },
        }
        result = apply_claude_code_settings(target, spec)

        self.assertIsNotNone(result["backup_path"])
        backup_path = Path(result["backup_path"])
        self.assertTrue(backup_path.exists())
        self.assertIn(".backup.", backup_path.name)

        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(saved["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:4000")
        self.assertEqual(
            saved["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"], "router-default"
        )
        self.assertEqual(saved["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "router-cheap")
        self.assertEqual(saved["env"]["ANTHROPIC_AUTH_TOKEN"], "your-gateway-token")
        self.assertEqual(saved["env"]["UNCHANGED_KEY"], "keep")
        self.assertEqual(saved["allowedTools"], ["Bash"])

    def test_apply_codex_updates_active_provider_base_url_and_preserves_other_sections(
        self,
    ):
        root = Path(tempfile.mkdtemp())
        target = root / "config.toml"
        target.write_text(
            "\n".join(
                [
                    'model_provider = "azure"',
                    'model = "gpt-5"',
                    "",
                    "[model_providers.azure]",
                    'name = "Azure"',
                    'base_url = "https://old.example/openai/v1"',
                    "",
                    "[mcp_servers.fetch]",
                    'command = "uvx"',
                ]
            ),
            encoding="utf-8",
        )

        spec = {"base_url": "http://127.0.0.1:4000/v1", "model": "router-default"}
        result = apply_codex_config(target, spec)

        self.assertIsNotNone(result["backup_path"])
        backup_path = Path(result["backup_path"])
        self.assertTrue(backup_path.exists())
        self.assertIn(".backup.", backup_path.name)

        saved = target.read_text(encoding="utf-8")
        self.assertIn('base_url = "http://127.0.0.1:4000/v1"', saved)
        self.assertIn("[mcp_servers.fetch]", saved)
        self.assertIn('command = "uvx"', saved)


if __name__ == "__main__":
    unittest.main()
