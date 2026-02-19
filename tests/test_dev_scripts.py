from __future__ import annotations

import os
import unittest
from pathlib import Path

import pytest


@pytest.mark.unit
class DevScriptTests(unittest.TestCase):
    def test_xgate_wraps_uvx_flowgate(self):
        path = Path("scripts/xgate")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn('UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"', text)
        self.assertIn('UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"', text)
        self.assertIn('uvx --from . flowgate "$@"', text)

    def test_xtest_wraps_uvx_pytest(self):
        """Test that xtest script uses pytest runner."""
        path = Path("scripts/xtest")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn('UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"', text)
        self.assertIn('UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"', text)
        self.assertIn("uvx --from . pytest tests/", text)

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
