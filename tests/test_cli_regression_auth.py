"""CLI 回归测试 - auth 命令组

验证 auth 命令的退出码和输出格式保持一致性。
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowgate.cli import run_cli


def write_minimal_config(path: Path) -> None:
    """创建最小化的测试配置文件"""
    data = {
        "paths": {
            "runtime_dir": str(path.parent / "runtime"),
            "active_config": str(path.parent / "runtime" / "litellm.active.yaml"),
            "state_file": str(path.parent / "runtime" / "state.json"),
            "log_file": str(path.parent / "logs" / "routerctl.log"),
        },
        "services": {
            "litellm": {
                "host": "127.0.0.1",
                "port": 4000,
                "command": {"args": ["litellm"]},
            },
            "cliproxyapi_plus": {
                "host": "127.0.0.1",
                "port": 5000,
                "command": {"args": ["CLIProxyAPIPlus"]},
            },
        },
        "litellm_base": {"litellm_settings": {"num_retries": 1}},
        "profiles": {
            "reliability": {"litellm_settings": {"num_retries": 3}},
        },
        "auth": {
            "providers": {
                "codex": {
                    "auth_url_endpoint": "http://example.local/codex/auth-url",
                    "status_endpoint": "http://example.local/codex/status",
                },
                "copilot": {
                    "auth_url_endpoint": "http://example.local/copilot/auth-url",
                    "status_endpoint": "http://example.local/copilot/status",
                },
            }
        },
        "secret_files": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class TestAuthCommandExitCodes(unittest.TestCase):
    """auth 命令退出码回归测试"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_minimal_config(self.cfg)

    def test_auth_list_success_exit_code(self):
        """auth list 成功时退出码为 0"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(
            result,
            0,
            f"期望退出码 0，实际 {result}\nstdout: {out.getvalue()}",
        )

    def test_auth_list_missing_config_exit_code(self):
        """auth list 缺少配置文件时退出码非 0"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", "/nonexistent/config.yaml", "auth", "list"],
            stdout=out,
            stderr=err,
        )
        self.assertNotEqual(result, 0, "期望非零退出码")
        self.assertTrue(err.getvalue() or "error" in out.getvalue().lower(), "期望有错误输出")

    def test_auth_status_success_exit_code(self):
        """auth status 成功时退出码为 0（即使没有认证）"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "status"], stdout=out)
        self.assertEqual(result, 0, f"stdout: {out.getvalue()}")

    def test_auth_login_invalid_provider_exit_code(self):
        """auth login 无效 provider 时退出码为 2"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            ["--config", str(self.cfg), "auth", "login", "nonexistent-provider", "--timeout", "1"],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 2, "期望退出码为 2（配置错误）")
        error_output = err.getvalue() + out.getvalue()
        self.assertTrue(
            "not configured" in error_output.lower() or "available=" in error_output,
            f"期望包含 provider 错误信息，实际输出: {error_output}",
        )

    def test_auth_login_timeout_exit_code(self):
        """auth login 超时时退出码为 1"""
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch("flowgate.cli.fetch_auth_url", return_value="https://example.com/login"),
            mock.patch(
                "flowgate.cli.poll_auth_status",
                side_effect=TimeoutError("OAuth login timed out"),
            ),
        ):
            result = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex", "--timeout", "1"],
                stdout=out,
                stderr=err,
            )
        self.assertEqual(result, 1, "期望退出码为 1（运行时错误）")
        self.assertIn("OAuth login failed", err.getvalue())

    def test_auth_import_headless_missing_source_exit_code(self):
        """auth import-headless 缺少 source 文件时退出码为 1"""
        out = io.StringIO()
        err = io.StringIO()
        result = run_cli(
            [
                "--config",
                str(self.cfg),
                "auth",
                "import-headless",
                "codex",
                "--source",
                "/nonexistent/auth.json",
            ],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(result, 1, "期望退出码为 1（文件不存在）")
        self.assertTrue(
            err.getvalue() or "failed" in out.getvalue().lower(),
            "期望有错误输出",
        )

    def test_auth_import_headless_invalid_json_exit_code(self):
        """auth import-headless 无效 JSON 文件时退出码为 1"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json{")
            invalid_json_path = f.name

        try:
            out = io.StringIO()
            err = io.StringIO()
            result = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "auth",
                    "import-headless",
                    "codex",
                    "--source",
                    invalid_json_path,
                ],
                stdout=out,
                stderr=err,
            )
            self.assertEqual(result, 1, "期望退出码为 1（JSON 解析错误）")
            self.assertTrue(err.getvalue(), "期望有错误输出")
        finally:
            Path(invalid_json_path).unlink(missing_ok=True)

    def test_auth_import_headless_unsupported_provider_exit_code(self):
        """auth import-headless 不支持的 provider 时退出码为 2"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            valid_json_path = f.name

        try:
            out = io.StringIO()
            err = io.StringIO()
            result = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "auth",
                    "import-headless",
                    "copilot",  # copilot 不支持 headless import
                    "--source",
                    valid_json_path,
                ],
                stdout=out,
                stderr=err,
            )
            self.assertEqual(result, 2, "期望退出码为 2（不支持的功能）")
            self.assertIn("not supported", err.getvalue())
        finally:
            Path(valid_json_path).unlink(missing_ok=True)


class TestAuthCommandOutput(unittest.TestCase):
    """auth 命令输出格式回归测试"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_minimal_config(self.cfg)

    def test_auth_list_output_format(self):
        """auth list 输出包含 providers 和能力信息"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(result, 0)

        output = out.getvalue()
        # 验证输出包含已配置的 providers
        self.assertIn("provider=codex", output, "输出应包含 codex provider")
        self.assertIn("provider=copilot", output, "输出应包含 copilot provider")

        # 验证输出包含能力信息
        self.assertIn("oauth_login=", output, "输出应包含 oauth_login 能力")
        self.assertIn("headless_import=", output, "输出应包含 headless_import 能力")

        # 验证汇总行
        self.assertIn("oauth_providers=", output, "输出应包含 oauth_providers 汇总")
        self.assertIn("headless_import_providers=", output, "输出应包含 headless_import_providers 汇总")

    def test_auth_status_output_format(self):
        """auth status 输出包含 default_auth_dir 和 provider 信息"""
        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "status"], stdout=out)
        self.assertEqual(result, 0)

        output = out.getvalue()
        # 验证输出包含关键字段
        self.assertIn("default_auth_dir=", output, "输出应包含 default_auth_dir")
        self.assertIn("secret_permission_issues=", output, "输出应包含 secret_permission_issues")
        self.assertIn("provider=codex", output, "输出应包含 codex provider")
        self.assertIn("method=", output, "输出应包含认证方法")

    def test_auth_login_success_output_format(self):
        """auth login 成功时输出包含 login_url 和 oauth_status"""
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.fetch_auth_url", return_value="https://example.com/login"),
            mock.patch("flowgate.cli.poll_auth_status", return_value="success"),
        ):
            result = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex", "--timeout", "5"],
                stdout=out,
            )
        self.assertEqual(result, 0)

        output = out.getvalue()
        self.assertIn("login_url=", output, "输出应包含 login_url")
        self.assertIn("https://example.com/login", output, "输出应包含实际的登录 URL")
        self.assertIn("oauth_status=", output, "输出应包含 oauth_status")

    def test_auth_import_headless_success_output_format(self):
        """auth import-headless 成功时输出包含 saved_auth 路径"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"token": "test-token", "expires_at": 9999999999}, f)
            valid_auth_path = f.name

        try:
            out = io.StringIO()
            handler = mock.Mock(return_value=Path("/tmp/auths/codex-headless-import.json"))
            with mock.patch("flowgate.cli.get_headless_import_handler", return_value=handler):
                result = run_cli(
                    [
                        "--config",
                        str(self.cfg),
                        "auth",
                        "import-headless",
                        "codex",
                        "--source",
                        valid_auth_path,
                    ],
                    stdout=out,
                )
            self.assertEqual(result, 0)

            output = out.getvalue()
            self.assertIn("saved_auth=", output, "输出应包含 saved_auth")
            self.assertIn("/tmp/auths/codex-headless-import.json", output, "输出应包含实际保存路径")
        finally:
            Path(valid_auth_path).unlink(missing_ok=True)

    def test_auth_login_error_output_contains_hint(self):
        """auth login 错误时输出包含调试提示"""
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch("flowgate.cli.fetch_auth_url", return_value="https://example.com/login"),
            mock.patch(
                "flowgate.cli.poll_auth_status",
                side_effect=TimeoutError("OAuth login timed out; last status=pending"),
            ),
        ):
            result = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex", "--timeout", "1"],
                stdout=out,
                stderr=err,
            )
        self.assertNotEqual(result, 0)

        error_output = err.getvalue()
        self.assertIn("hint=", error_output, "错误输出应包含调试提示")
        self.assertIn("auth status", error_output, "提示应建议运行 auth status")

    def test_auth_list_empty_providers_output(self):
        """auth list 没有配置 providers 时的输出格式"""
        # 创建没有 auth providers 的配置
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["auth"]["providers"] = {}
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        result = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(result, 0)

        output = out.getvalue()
        self.assertIn("oauth_providers=none", output, "没有 providers 时应输出 none")
        self.assertIn("headless_import_providers=none", output, "没有 headless providers 时应输出 none")


if __name__ == "__main__":
    unittest.main()
