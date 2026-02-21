import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowgate.cli import run_cli
from flowgate.cli.parser import build_parser
from flowgate.constants import (
    DEFAULT_READINESS_PATH,
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORTS,
    DEFAULT_SERVICE_READINESS_PATHS,
)
from tests.fixtures import ConfigFactory

import pytest

class TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def write_config(path: Path) -> None:
    """Write test config using ConfigFactory."""
    data = ConfigFactory.with_profiles(["reliability", "balanced", "cost"])
    data["paths"] = ConfigFactory.paths(
        runtime_dir=str(path.parent / "runtime"),
        active_config=str(path.parent / "runtime" / "litellm.active.yaml"),
        state_file=str(path.parent / "runtime" / "state.json"),
        log_file=str(path.parent / "logs" / "routerctl.log"),
    )
    data["auth"] = {
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
    }
    data["secret_files"] = []

    path.write_text(json.dumps(data), encoding="utf-8")
@pytest.mark.unit
class CLITests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = self.root / "flowgate.yaml"
        write_config(self.cfg)

    def test_profile_list_and_set(self):
        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "profile", "list"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("balanced", out.getvalue())

        out = io.StringIO()
        code = run_cli(
            ["--config", str(self.cfg), "profile", "set", "balanced"], stdout=out
        )
        self.assertEqual(code, 0)

        state_file = self.root / "runtime" / "state.json"
        self.assertTrue(state_file.exists())
        state = json.loads(state_file.read_text())
        self.assertEqual(state["current_profile"], "balanced")

    def test_status_command(self):
        run_cli(
            ["--config", str(self.cfg), "profile", "set", "reliability"],
            stdout=io.StringIO(),
        )

        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "status"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("current_profile=reliability", text)

    def test_profile_set_restarts_litellm_when_running(self):
        out = io.StringIO()
        with mock.patch("flowgate.cli.ProcessSupervisor") as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = True
            supervisor.restart.return_value = 4321

            code = run_cli(
                ["--config", str(self.cfg), "profile", "set", "balanced"], stdout=out
            )

        self.assertEqual(code, 0)
        supervisor.is_running.assert_called_once_with("litellm")
        supervisor.restart.assert_called_once()
        supervisor.record_event.assert_called_once_with(
            "profile_switch", profile="balanced", result="success"
        )
        self.assertIn("litellm:restarted pid=4321", out.getvalue())

    def test_health_command(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.check_http_health",
                side_effect=lambda url, timeout=1.0: {
                    "ok": str(DEFAULT_SERVICE_PORTS["litellm"]) in url,
                    "status_code": 200
                    if str(DEFAULT_SERVICE_PORTS["litellm"]) in url
                    else 503,
                    "error": None,
                },
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.side_effect = [True, True]
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)
        self.assertEqual(code, 1)
        text = out.getvalue()
        # New format includes service health section
        self.assertIn("Service Health:", text)
        self.assertIn("litellm: liveness=ok readiness=ok", text)
        self.assertIn("cliproxyapi_plus: liveness=ok readiness=fail", text)

    def test_health_command_uses_default_readiness_path_when_missing(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        for service in data["services"].values():
            service.pop("readiness_path", None)
            service.pop("health_path", None)
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.check_http_health",
                return_value={"ok": True, "status_code": 200, "error": None},
            ) as checker,
            mock.patch(
                "flowgate.health.comprehensive_health_check",
                return_value={
                    "overall_status": "healthy",
                    "status_counts": {"healthy": 4, "degraded": 0, "unhealthy": 0},
                    "checks": {
                        "disk_space": {"status": "healthy", "message": "OK", "details": {}},
                        "memory": {"status": "healthy", "message": "OK", "details": {}},
                        "credentials": {"status": "healthy", "message": "OK", "details": {}},
                        "port_conflicts": {"status": "healthy", "message": "OK", "details": {}},
                    },
                },
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.side_effect = [True, True]
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)

        self.assertEqual(code, 0)
        checked_urls = [call.args[0] for call in checker.call_args_list]
        self.assertEqual(
            checked_urls,
            [
                f"http://{DEFAULT_SERVICE_HOST}:{DEFAULT_SERVICE_PORTS['cliproxyapi_plus']}{DEFAULT_READINESS_PATH}",
                f"http://{DEFAULT_SERVICE_HOST}:{DEFAULT_SERVICE_PORTS['litellm']}{DEFAULT_READINESS_PATH}",
            ],
        )

    def test_health_command_fails_when_service_not_running(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.check_http_health",
                return_value={"ok": True, "status_code": 200, "error": None},
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.side_effect = [True, False]
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)
        self.assertEqual(code, 1)
        # New format: service name followed by status
        self.assertIn("litellm: liveness=fail readiness=ok", out.getvalue())

    def test_service_start_stop_all(self):
        out = io.StringIO()
        with mock.patch("flowgate.cli.commands.service.ProcessSupervisor") as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.start.side_effect = [111, 222]
            code = run_cli(
                ["--config", str(self.cfg), "service", "start", "all"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertIn("litellm:started pid=111", out.getvalue())
        self.assertIn("cliproxyapi_plus:started pid=222", out.getvalue())

        out = io.StringIO()
        with mock.patch("flowgate.cli.commands.service.ProcessSupervisor") as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.stop.side_effect = [True, True]
            code = run_cli(
                ["--config", str(self.cfg), "service", "stop", "all"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertIn("litellm:stopped", out.getvalue())
        self.assertIn("cliproxyapi_plus:stopped", out.getvalue())

    def test_service_start_reports_port_in_use(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((DEFAULT_SERVICE_HOST, 0))
            occupied.listen(1)
            data["services"]["cliproxyapi_plus"]["port"] = occupied.getsockname()[1]
            self.cfg.write_text(json.dumps(data), encoding="utf-8")

            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("flowgate.cli.commands.service.ProcessSupervisor") as supervisor_cls:
                supervisor = supervisor_cls.return_value
                supervisor.is_running.return_value = False
                code = run_cli(
                    ["--config", str(self.cfg), "service", "start", "cliproxyapi_plus"],
                    stdout=out,
                    stderr=err,
                )

        self.assertEqual(code, 1)
        self.assertIn("port-in-use", err.getvalue())
        self.assertIn("cliproxyapi_plus", err.getvalue())
        supervisor.start.assert_not_called()

    def test_service_restart_reports_port_in_use_when_service_not_running(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((DEFAULT_SERVICE_HOST, 0))
            occupied.listen(1)
            data["services"]["cliproxyapi_plus"]["port"] = occupied.getsockname()[1]
            self.cfg.write_text(json.dumps(data), encoding="utf-8")

            out = io.StringIO()
            err = io.StringIO()
            with mock.patch("flowgate.cli.commands.service.ProcessSupervisor") as supervisor_cls:
                supervisor = supervisor_cls.return_value
                supervisor.is_running.return_value = False
                code = run_cli(
                    [
                        "--config",
                        str(self.cfg),
                        "service",
                        "restart",
                        "cliproxyapi_plus",
                    ],
                    stdout=out,
                    stderr=err,
                )

        self.assertEqual(code, 1)
        self.assertIn("port-in-use", err.getvalue())
        self.assertIn("cliproxyapi_plus", err.getvalue())
        supervisor.restart.assert_not_called()

    def test_auth_login(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.commands.auth.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.oauth.fetch_auth_url", return_value="https://example.com/login"
            ) as f_url,
            mock.patch(
                "flowgate.oauth.poll_auth_status", return_value="success"
            ) as p_status,
        ):
            code = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertIn("https://example.com/login", out.getvalue())
        f_url.assert_called_once()
        p_status.assert_called_once()
        supervisor = supervisor_cls.return_value
        supervisor.record_event.assert_called_once_with(
            "oauth_login",
            provider="codex",
            result="success",
        )

    def test_auth_login_timeout_error_contains_hint(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch("flowgate.cli.commands.auth.ProcessSupervisor"),
            mock.patch(
                "flowgate.oauth.fetch_auth_url", return_value="https://example.com/login"
            ),
            mock.patch(
                "flowgate.oauth.poll_auth_status",
                side_effect=TimeoutError("OAuth login timed out; last status=pending"),
            ),
        ):
            code = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex"],
                stdout=out,
                stderr=err,
            )
        self.assertEqual(code, 1)
        self.assertIn("last status=pending", err.getvalue())
        self.assertIn("hint=", err.getvalue())

    def test_auth_list_reports_configured_providers_and_headless_support(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["auth"]["providers"]["custom"] = {
            "auth_url_endpoint": "http://example.local/custom/auth-url",
            "status_endpoint": "http://example.local/custom/status",
        }
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "auth", "list"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("provider=codex oauth_login=yes headless_import=yes", text)
        self.assertIn("provider=copilot oauth_login=yes headless_import=no", text)
        self.assertIn("provider=custom oauth_login=yes headless_import=no", text)

    def test_auth_status_reports_provider_capabilities(self):
        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "auth", "status"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("provider=codex", text)
        self.assertIn("default_auth_dir=", text)

    def test_auth_login_generic_provider_command(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["auth"]["providers"]["custom"] = {
            "auth_url_endpoint": "http://example.local/custom/auth-url",
            "status_endpoint": "http://example.local/custom/status",
        }
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.commands.auth.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.oauth.fetch_auth_url",
                return_value="https://example.com/custom-login",
            ) as f_url,
            mock.patch(
                "flowgate.oauth.poll_auth_status", return_value="success"
            ) as p_status,
        ):
            code = run_cli(
                ["--config", str(self.cfg), "auth", "login", "custom"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertIn("login_url=https://example.com/custom-login", out.getvalue())
        f_url.assert_called_once_with("http://example.local/custom/auth-url", timeout=5)
        p_status.assert_called_once_with(
            "http://example.local/custom/status",
            timeout_seconds=120,
            poll_interval_seconds=2,
        )
        supervisor = supervisor_cls.return_value
        supervisor.record_event.assert_called_once_with(
            "oauth_login",
            provider="custom",
            result="success",
        )

    def test_auth_import_headless_generic_provider_command(self):
        out = io.StringIO()
        handler = mock.Mock(return_value=Path("/tmp/auths/codex-headless-import.json"))
        with mock.patch(
            "flowgate.auth_methods.get_headless_import_handler", return_value=handler
        ) as resolver:
            code = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "auth",
                    "import-headless",
                    "codex",
                    "--source",
                    "/tmp/codex-auth.json",
                ],
                stdout=out,
            )
        self.assertEqual(code, 0)
        self.assertIn(
            "saved_auth=/tmp/auths/codex-headless-import.json", out.getvalue()
        )
        resolver.assert_called_once_with("codex")
        handler.assert_called_once_with(
            "/tmp/codex-auth.json", str((self.root / "auths").resolve())
        )

    def test_auth_import_dispatches_by_registered_method(self):
        out = io.StringIO()
        handler = mock.Mock(return_value=Path("/tmp/auths/custom-headless-import.json"))
        with (
            mock.patch(
                "flowgate.auth_methods.get_headless_import_handler", return_value=handler
            ) as resolver,
            mock.patch("flowgate.cli.commands.auth.ProcessSupervisor") as supervisor_cls,
        ):
            code = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "auth",
                    "import-headless",
                    "custom",
                    "--source",
                    "/tmp/custom-auth.json",
                ],
                stdout=out,
            )
        self.assertEqual(code, 0)
        self.assertIn(
            "saved_auth=/tmp/auths/custom-headless-import.json", out.getvalue()
        )
        resolver.assert_called_once_with("custom")
        handler.assert_called_once_with(
            "/tmp/custom-auth.json", str((self.root / "auths").resolve())
        )
        supervisor = supervisor_cls.return_value
        supervisor.record_event.assert_called_once()

    def test_auth_login_generic_command_unknown_provider(self):
        out = io.StringIO()
        err = io.StringIO()
        code = run_cli(
            ["--config", str(self.cfg), "auth", "login", "unknown-provider"],
            stdout=out,
            stderr=err,
        )
        self.assertEqual(code, 2)
        self.assertIn("OAuth provider not configured: unknown-provider", err.getvalue())
        self.assertIn("available=", err.getvalue())

    def test_status_detects_default_auth_dir_permission_issues(self):
        auth_dir = self.root / "auths"
        auth_dir.mkdir(parents=True, exist_ok=True)
        imported_auth = auth_dir / "codex-headless-import.json"
        imported_auth.write_text("{}", encoding="utf-8")
        os.chmod(imported_auth, 0o644)

        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg), "status"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("secret_permission_issues=1", out.getvalue())

    def test_auth_codex_import_headless(self):
        out = io.StringIO()
        handler = mock.Mock(return_value=Path("/tmp/auths/codex-headless-import.json"))
        with mock.patch(
            "flowgate.auth_methods.get_headless_import_handler", return_value=handler
        ) as resolver:
            code = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "auth",
                    "import-headless",
                    "codex",
                    "--source",
                    "/tmp/codex-auth.json",
                ],
                stdout=out,
            )
        self.assertEqual(code, 0)
        self.assertIn(
            "saved_auth=/tmp/auths/codex-headless-import.json", out.getvalue()
        )
        resolver.assert_called_once_with("codex")
        handler.assert_called_once()

    def test_auth_codex_import_headless_default_dest_follows_runtime_root(self):
        cfg_dir = self.root / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "flowgate.yaml"

        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["paths"]["runtime_dir"] = "../.router/runtime"
        data["paths"]["active_config"] = "../.router/runtime/litellm.active.yaml"
        data["paths"]["state_file"] = "../.router/runtime/state.json"
        data["paths"]["log_file"] = "../.router/logs/routerctl.log"
        cfg_path.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        handler = mock.Mock(return_value=Path("/tmp/auths/codex-headless-import.json"))
        with mock.patch(
            "flowgate.auth_methods.get_headless_import_handler", return_value=handler
        ) as resolver:
            code = run_cli(
                [
                    "--config",
                    str(cfg_path),
                    "auth",
                    "import-headless",
                    "codex",
                    "--source",
                    "/tmp/codex-auth.json",
                ],
                stdout=out,
            )

        self.assertEqual(code, 0)
        self.assertIn(
            "saved_auth=/tmp/auths/codex-headless-import.json", out.getvalue()
        )
        expected_dest = str((self.root / ".router" / "auths").resolve())
        resolver.assert_called_once_with("codex")
        handler.assert_called_once_with("/tmp/codex-auth.json", expected_dest)

    def test_bootstrap_download(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.commands.bootstrap.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ) as cliproxy_download,
            mock.patch(
                "flowgate.cli.commands.bootstrap.prepare_litellm_runner",
                return_value=Path("/tmp/runtime/bin/litellm"),
            ) as litellm_prepare,
            mock.patch(
                "flowgate.cli.commands.bootstrap.validate_cliproxy_binary", return_value=True
            ) as cliproxy_validate,
            mock.patch(
                "flowgate.cli.commands.bootstrap.validate_litellm_runner", return_value=True
            ) as litellm_validate,
        ):
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "download"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertIn(
            "cliproxyapi_plus=/tmp/runtime/bin/CLIProxyAPIPlus", out.getvalue()
        )
        self.assertIn("litellm=/tmp/runtime/bin/litellm", out.getvalue())
        cliproxy_download.assert_called_once()
        litellm_prepare.assert_called_once()
        cliproxy_validate.assert_called_once()
        litellm_validate.assert_called_once()

    def test_bootstrap_download_rejects_litellm_version_flag(self):
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["bootstrap", "download", "--litellm-version", "1.2.3"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_parser_prog_name_is_flowgate(self):
        parser = build_parser()
        self.assertIn("flowgate", parser.format_usage())

    def test_integration_print_codex(self):
        out = io.StringIO()

        code = run_cli(
            ["--config", str(self.cfg), "integration", "print", "codex"],
            stdout=out,
        )

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn('model_provider = "flowgate"', text)
        self.assertIn("[model_providers.flowgate]", text)
        self.assertIn('base_url = "http://127.0.0.1:4000/v1"', text)
        self.assertIn('model = "router-default"', text)

    def test_integration_print_claude_code(self):
        out = io.StringIO()

        code = run_cli(
            ["--config", str(self.cfg), "integration", "print", "claude-code"],
            stdout=out,
        )

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("ANTHROPIC_BASE_URL=http://127.0.0.1:4000", text)
        self.assertIn("ANTHROPIC_AUTH_TOKEN=your-gateway-token", text)
        self.assertIn("ANTHROPIC_DEFAULT_SONNET_MODEL=router-default", text)
        self.assertIn("ANTHROPIC_DEFAULT_HAIKU_MODEL=router-default", text)

    def test_integration_apply_claude_code(self):
        target = self.root / "claude-settings.json"
        target.write_text(
            json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": "old"}}),
            encoding="utf-8",
        )

        out = io.StringIO()
        code = run_cli(
            [
                "--config",
                str(self.cfg),
                "integration",
                "apply",
                "claude-code",
                "--target",
                str(target),
            ],
            stdout=out,
        )

        self.assertEqual(code, 0)
        self.assertIn(f"saved_path={target}", out.getvalue())
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(saved["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:4000")
        self.assertEqual(saved["env"]["ANTHROPIC_AUTH_TOKEN"], "your-gateway-token")

    def test_doctor_reports_missing_runtime_artifacts(self):
        out = io.StringIO()
        with mock.patch(
            "flowgate.cli._runtime_dependency_available", return_value=True
        ):
            code = run_cli(["--config", str(self.cfg), "doctor"], stdout=out)
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("doctor:runtime_dir=fail", text)
        self.assertIn("doctor:runtime_binaries=fail", text)

    def test_doctor_passes_when_runtime_ready(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        secret_dir = self.root / "auths"
        secret_dir.mkdir(parents=True, exist_ok=True)
        secret_file = secret_dir / "codex.json"
        secret_file.write_text("{}", encoding="utf-8")
        os.chmod(secret_file, 0o600)
        data["secret_files"] = [str(secret_file)]
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        runtime_bin = self.root / "runtime" / "bin"
        runtime_bin.mkdir(parents=True, exist_ok=True)
        cliproxy = runtime_bin / "CLIProxyAPIPlus"
        litellm = runtime_bin / "litellm"
        cliproxy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        litellm.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cliproxy, 0o755)
        os.chmod(litellm, 0o755)

        out = io.StringIO()
        with mock.patch(
            "flowgate.cli._runtime_dependency_available", return_value=True
        ):
            code = run_cli(["--config", str(self.cfg), "doctor"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("doctor:runtime_dir=pass", text)
        self.assertIn("doctor:runtime_binaries=pass", text)
        self.assertIn("doctor:secret_permissions=pass", text)
        self.assertIn("doctor:runtime_dependency=pass", text)

    def test_doctor_fails_when_api_key_ref_credential_file_missing(self):
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["credentials"] = {
            "upstream": {
                "coproxy_local": {"file": str(self.root / "secrets" / "missing.key")}
            }
        }
        data["litellm_base"]["model_list"] = [
            {
                "model_name": "router-default",
                "litellm_params": {
                    "model": "openai/router-default",
                    "api_key_ref": "coproxy_local",
                },
            }
        ]
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        runtime_bin = self.root / "runtime" / "bin"
        runtime_bin.mkdir(parents=True, exist_ok=True)
        cliproxy = runtime_bin / "CLIProxyAPIPlus"
        litellm = runtime_bin / "litellm"
        cliproxy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        litellm.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cliproxy, 0o755)
        os.chmod(litellm, 0o755)

        out = io.StringIO()
        with mock.patch(
            "flowgate.cli._runtime_dependency_available", return_value=True
        ):
            code = run_cli(["--config", str(self.cfg), "doctor"], stdout=out)
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("doctor:upstream_credentials=fail", text)

    def test_service_start_reports_cliproxyapiplus_update_when_available(self):
        out = TTYStringIO()
        with (
            mock.patch("flowgate.cli.commands.service.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cliproxyapiplus_update_check.read_cliproxyapiplus_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cliproxyapiplus_update_check.check_cliproxyapiplus_update",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "https://github.com/router-for-me/CLIProxyAPIPlus/releases/tag/v6.8.18-1",
                },
            ) as checker,
        ):
            supervisor = supervisor_cls.return_value
            supervisor.start.side_effect = [111, 222]
            code = run_cli(
                ["--config", str(self.cfg), "service", "start", "all"], stdout=out
            )

        self.assertEqual(code, 0)
        self.assertIn("cliproxyapi_plus:update_available", out.getvalue())
        self.assertIn("latest=v6.8.18-1", out.getvalue())
        checker.assert_called_once()

    def test_doctor_reports_cliproxyapiplus_update_when_available(self):
        runtime_bin = self.root / "runtime" / "bin"
        runtime_bin.mkdir(parents=True, exist_ok=True)
        cliproxy = runtime_bin / "CLIProxyAPIPlus"
        litellm = runtime_bin / "litellm"
        cliproxy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        litellm.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cliproxy, 0o755)
        os.chmod(litellm, 0o755)

        out = TTYStringIO()
        with (
            mock.patch("flowgate.cli._runtime_dependency_available", return_value=True),
            mock.patch(
                "flowgate.cliproxyapiplus_update_check.read_cliproxyapiplus_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cliproxyapiplus_update_check.check_cliproxyapiplus_update",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "https://github.com/router-for-me/CLIProxyAPIPlus/releases/tag/v6.8.18-1",
                },
            ) as checker,
        ):
            code = run_cli(["--config", str(self.cfg), "doctor"], stdout=out)

        self.assertEqual(code, 0)
        self.assertIn("cliproxyapi_plus:update_available", out.getvalue())
        self.assertIn("latest=v6.8.18-1", out.getvalue())
        checker.assert_called_once()


if __name__ == "__main__":
    unittest.main()
