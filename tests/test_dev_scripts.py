from __future__ import annotations

import os
import unittest
from pathlib import Path

import pytest


@pytest.mark.unit
class DevScriptTests(unittest.TestCase):
    def test_common_sh_defines_env_vars(self):
        path = Path("scripts/_common.sh")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn('UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"', text)
        self.assertIn('UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"', text)
        self.assertIn("check_help", text)
        self.assertIn("run_or_help", text)

    def test_xgate_sources_common_and_runs_flowgate(self):
        path = Path("scripts/xgate")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn("_common.sh", text)
        self.assertIn("show_help", text)
        self.assertIn('uv run flowgate "$@"', text)

    def test_xtest_sources_common_and_runs_pytest(self):
        """Test that xtest script uses pytest runner."""
        path = Path("scripts/xtest")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn("_common.sh", text)
        self.assertIn("show_help", text)
        self.assertIn("uv run pytest tests/", text)

    def test_smoke_script_has_claude_messages_probe(self):
        path = Path("scripts/smoke_local.sh")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("/v1/messages/count_tokens", text)
        self.assertIn("anthropic-version: 2023-06-01", text)
        self.assertIn("SMOKE_UPSTREAM_CLIPROXY_API_KEY", text)
        self.assertIn("ensure_upstream_api_key_file", text)


if __name__ == "__main__":
    unittest.main()
