import stat
import tempfile
import unittest
import io
import tarfile
from pathlib import Path
from unittest import mock

from flowgate.bootstrap import (
    _extract_binary_from_bytes,
    detect_platform,
    pick_release_asset,
    prepare_litellm_runner,
    validate_cliproxy_binary,
    validate_litellm_runner,
)


class BootstrapTests(unittest.TestCase):
    def test_detect_platform_darwin_arm64(self):
        with (
            mock.patch("flowgate.bootstrap.platform.system", return_value="Darwin"),
            mock.patch("flowgate.bootstrap.platform.machine", return_value="arm64"),
        ):
            os_name, arch = detect_platform()
        self.assertEqual(os_name, "darwin")
        self.assertEqual(arch, "arm64")

    def test_detect_platform_linux_amd64(self):
        with (
            mock.patch("flowgate.bootstrap.platform.system", return_value="Linux"),
            mock.patch("flowgate.bootstrap.platform.machine", return_value="x86_64"),
        ):
            os_name, arch = detect_platform()
        self.assertEqual(os_name, "linux")
        self.assertEqual(arch, "amd64")

    def test_pick_release_asset_prefers_platform_match(self):
        assets = [
            {
                "name": "CLIProxyAPIPlus_linux_amd64.tar.gz",
                "browser_download_url": "https://example/linux",
            },
            {
                "name": "CLIProxyAPIPlus_darwin_arm64.tar.gz",
                "browser_download_url": "https://example/darwin",
            },
        ]
        picked = pick_release_asset(assets, os_name="darwin", arch="arm64")
        self.assertEqual(picked["browser_download_url"], "https://example/darwin")

    def test_prepare_litellm_runner(self):
        root = Path(tempfile.mkdtemp())
        runner = prepare_litellm_runner(root, version="1.75.8")

        self.assertTrue(runner.exists())
        text = runner.read_text(encoding="utf-8")
        self.assertIn("uv run --project", text)
        self.assertIn('litellm "$@"', text)
        self.assertIn("runtime", text)
        mode = stat.S_IMODE(runner.stat().st_mode)
        self.assertEqual(mode, 0o755)
        self.assertTrue(validate_litellm_runner(runner))

    def test_validate_litellm_runner_accepts_no_runtime_group_script(self):
        root = Path(tempfile.mkdtemp())
        runner = root / "litellm"
        runner.write_text(
            (
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'project_root="$(cd "$(dirname "$0")/../../.." && pwd)"\n'
                'exec uv run --project "$project_root" litellm "$@"\n'
            ),
            encoding="utf-8",
        )
        runner.chmod(0o755)

        self.assertTrue(validate_litellm_runner(runner))

    def test_extract_binary_prefers_cli_proxy_executable(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            lic = tarfile.TarInfo(name="LICENSE")
            lic_data = b"MIT License\\n"
            lic.size = len(lic_data)
            lic.mode = 0o644
            tf.addfile(lic, io.BytesIO(lic_data))

            exe = tarfile.TarInfo(name="cli-proxy-api-plus")
            exe_data = b"ELF_BINARY_PLACEHOLDER"
            exe.size = len(exe_data)
            exe.mode = 0o755
            tf.addfile(exe, io.BytesIO(exe_data))

        extracted = _extract_binary_from_bytes(
            buf.getvalue(), "CLIProxyAPIPlus_6.8.18-1_linux_amd64.tar.gz"
        )
        self.assertEqual(extracted, b"ELF_BINARY_PLACEHOLDER")

    def test_validate_cliproxy_binary(self):
        root = Path(tempfile.mkdtemp())
        binary = root / "CLIProxyAPIPlus"
        binary.write_bytes(b"\x00" * (1_200_000))
        binary.chmod(0o755)

        self.assertTrue(validate_cliproxy_binary(binary))

        tiny = root / "tiny"
        tiny.write_bytes(b"MIT License")
        tiny.chmod(0o755)
        self.assertFalse(validate_cliproxy_binary(tiny))


if __name__ == "__main__":
    unittest.main()
