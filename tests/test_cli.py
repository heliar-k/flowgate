import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from llm_router.cli import run_cli


def write_config(path: Path) -> None:
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
                "health_path": "/healthz",
                "command": {"args": ["python", "-c", "import time; time.sleep(60)"]},
            },
            "cliproxyapi_plus": {
                "host": "127.0.0.1",
                "port": 8317,
                "health_path": "/healthz",
                "command": {"args": ["python", "-c", "import time; time.sleep(60)"]},
            },
        },
        "litellm_base": {"litellm_settings": {"num_retries": 1}},
        "profiles": {
            "reliability": {"litellm_settings": {"num_retries": 3}},
            "balanced": {"litellm_settings": {"num_retries": 2}},
            "cost": {"litellm_settings": {"num_retries": 1}},
        },
        "oauth": {
            "codex": {
                "auth_url_endpoint": "http://example.local/codex/auth-url",
                "status_endpoint": "http://example.local/codex/status",
            },
            "copilot": {
                "auth_url_endpoint": "http://example.local/copilot/auth-url",
                "status_endpoint": "http://example.local/copilot/status",
            },
        },
        "secret_files": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


class CLITests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "routertool.yaml"
        write_config(self.cfg)

    def test_profile_list_and_set(self):
        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "profile", "list"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("balanced", out.getvalue())

        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "profile", "set", "balanced"], stdout=out)
        self.assertEqual(code, 0)

        state_file = self.root / "runtime" / "state.json"
        self.assertTrue(state_file.exists())
        state = json.loads(state_file.read_text())
        self.assertEqual(state["current_profile"], "balanced")

    def test_status_command(self):
        run_cli(["--config", str(self.cfg), "profile", "set", "reliability"], stdout=io.StringIO())

        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "status"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("current_profile=reliability", text)

    def test_profile_set_restarts_litellm_when_running(self):
        out = io.StringIO()
        with mock.patch("llm_router.cli.ProcessSupervisor") as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = True
            supervisor.restart.return_value = 4321

            code = run_cli(["--config", str(self.cfg), "profile", "set", "balanced"], stdout=out)

        self.assertEqual(code, 0)
        supervisor.is_running.assert_called_once_with("litellm")
        supervisor.restart.assert_called_once()
        self.assertIn("litellm:restarted pid=4321", out.getvalue())

    def test_health_command(self):
        out = io.StringIO()
        with mock.patch(
            "llm_router.cli.check_health_url",
            side_effect=lambda url, timeout=1.0: "4000" in url,
        ):
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("litellm:ok", text)
        self.assertIn("cliproxyapi_plus:fail", text)

    def test_service_start_stop_all(self):
        out = io.StringIO()
        with mock.patch("llm_router.cli.ProcessSupervisor") as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.start.side_effect = [111, 222]
            code = run_cli(["--config", str(self.cfg), "service", "start", "all"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("litellm:started pid=111", out.getvalue())
        self.assertIn("cliproxyapi_plus:started pid=222", out.getvalue())

        out = io.StringIO()
        with mock.patch("llm_router.cli.ProcessSupervisor") as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.stop.side_effect = [True, True]
            code = run_cli(["--config", str(self.cfg), "service", "stop", "all"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("litellm:stopped", out.getvalue())
        self.assertIn("cliproxyapi_plus:stopped", out.getvalue())

    def test_auth_login(self):
        out = io.StringIO()
        with (
            mock.patch("llm_router.cli.fetch_auth_url", return_value="https://example.com/login") as f_url,
            mock.patch("llm_router.cli.poll_auth_status", return_value="success") as p_status,
        ):
            code = run_cli(["--config", str(self.cfg), "auth", "codex", "login"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("https://example.com/login", out.getvalue())
        f_url.assert_called_once()
        p_status.assert_called_once()

    def test_bootstrap_download(self):
        out = io.StringIO()
        with (
            mock.patch(
                "llm_router.cli.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ) as cliproxy_download,
            mock.patch(
                "llm_router.cli.prepare_litellm_runner",
                return_value=Path("/tmp/runtime/bin/litellm"),
            ) as litellm_prepare,
            mock.patch("llm_router.cli.validate_cliproxy_binary", return_value=True) as cliproxy_validate,
            mock.patch("llm_router.cli.validate_litellm_runner", return_value=True) as litellm_validate,
        ):
            code = run_cli(["--config", str(self.cfg), "bootstrap", "download"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("cliproxyapi_plus=/tmp/runtime/bin/CLIProxyAPIPlus", out.getvalue())
        self.assertIn("litellm=/tmp/runtime/bin/litellm", out.getvalue())
        cliproxy_download.assert_called_once()
        litellm_prepare.assert_called_once()
        cliproxy_validate.assert_called_once()
        litellm_validate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
