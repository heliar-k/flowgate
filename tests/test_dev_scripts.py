from __future__ import annotations

import os
import unittest
from pathlib import Path


class DevScriptTests(unittest.TestCase):
    def test_xgate_wraps_uvx_flowgate(self):
        path = Path("scripts/xgate")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn('UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"', text)
        self.assertIn('UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"', text)
        self.assertIn('uvx --from . flowgate "$@"', text)

    def test_xtest_wraps_uvx_unittest(self):
        path = Path("scripts/xtest")
        self.assertTrue(path.exists())
        self.assertTrue(os.access(path, os.X_OK))
        text = path.read_text(encoding="utf-8")
        self.assertIn('UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"', text)
        self.assertIn('UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"', text)
        self.assertIn("uvx --from . python -m unittest discover -s tests -v", text)


if __name__ == "__main__":
    unittest.main()
