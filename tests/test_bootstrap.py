import stat
import tempfile
import unittest
from pathlib import Path

from llm_router.bootstrap import pick_release_asset, prepare_litellm_runner


class BootstrapTests(unittest.TestCase):
    def test_pick_release_asset_prefers_platform_match(self):
        assets = [
            {"name": "CLIProxyAPIPlus_linux_amd64.tar.gz", "browser_download_url": "https://example/linux"},
            {"name": "CLIProxyAPIPlus_darwin_arm64.tar.gz", "browser_download_url": "https://example/darwin"},
        ]
        picked = pick_release_asset(assets, os_name="darwin", arch="arm64")
        self.assertEqual(picked["browser_download_url"], "https://example/darwin")

    def test_prepare_litellm_runner(self):
        root = Path(tempfile.mkdtemp())
        runner = prepare_litellm_runner(root, version="1.75.8")

        self.assertTrue(runner.exists())
        text = runner.read_text(encoding="utf-8")
        self.assertIn('litellm==1.75.8', text)
        mode = stat.S_IMODE(runner.stat().st_mode)
        self.assertEqual(mode, 0o755)


if __name__ == "__main__":
    unittest.main()
