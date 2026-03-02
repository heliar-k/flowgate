import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from flowgate.cli import run_cli
from flowgate.cli.parser import build_parser
from flowgate.constants import (
    DEFAULT_READINESS_PATH,
)


class TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def write_minimal_v3_config(root: Path) -> Path:
    """Write a minimal config_version 3 config (cliproxy-only)."""
    cfg_dir = root / "config-v3"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    cliproxy_cfg = cfg_dir / "cliproxyapi.yaml"
    cliproxy_cfg.write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                "port": 5000,
                "api-keys": ["sk-local-test"],
                "remote-management": {"secret-key": "x"},
            }
        ),
        encoding="utf-8",
    )

    runtime_dir = root / "runtime-v3"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    flowgate_cfg = cfg_dir / "flowgate.yaml"
    flowgate_cfg.write_text(
        json.dumps(
            {
                "config_version": 3,
                "paths": {
                    "runtime_dir": str(runtime_dir),
                    "log_file": str(runtime_dir / "events.log"),
                },
                "cliproxyapi_plus": {"config_file": str(cliproxy_cfg)},
                "auth": {
                    "providers": {
                        "codex": {
                            "method": "oauth_poll",
                            "auth_url_endpoint": "http://example.local/codex/auth-url",
                            "status_endpoint": "http://example.local/codex/status",
                        },
                        "copilot": {
                            "method": "oauth_poll",
                            "auth_url_endpoint": "http://example.local/copilot/auth-url",
                            "status_endpoint": "http://example.local/copilot/status",
                        },
                    }
                },
                "secret_files": [],
            }
        ),
        encoding="utf-8",
    )
    return flowgate_cfg


@pytest.mark.unit
def test_profile_command_is_removed() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["profile", "list"])
    assert exc.value.code == 2


@pytest.mark.unit
class CLITests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg = write_minimal_v3_config(self.root)

    def test_health_command(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.health.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.health.check_http_health",
                return_value={"ok": True, "status_code": 200, "error": None},
            ),
            mock.patch(
                "flowgate.cli.health.comprehensive_health_check",
                return_value={
                    "overall_status": "healthy",
                    "status_counts": {"healthy": 4, "degraded": 0, "unhealthy": 0},
                    "checks": {},
                },
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = True
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        # New format includes service health section
        self.assertIn("Service Health:", text)
        self.assertIn("cliproxyapi_plus: liveness=ok readiness=ok", text)

    def test_health_command_json(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.health.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.health.check_http_health",
                return_value={"ok": True, "status_code": 200, "error": None},
            ),
            mock.patch(
                "flowgate.cli.health.comprehensive_health_check",
                return_value={
                    "overall_status": "degraded",
                    "status_counts": {"healthy": 3, "degraded": 1, "unhealthy": 0},
                    "checks": {
                        "disk_space": {
                            "status": "healthy",
                            "message": "OK",
                            "details": {},
                        },
                        "memory": {"status": "healthy", "message": "OK", "details": {}},
                        "credentials": {
                            "status": "healthy",
                            "message": "OK",
                            "details": {},
                        },
                        "port_conflicts": {
                            "status": "degraded",
                            "message": "WARN",
                            "details": {},
                        },
                    },
                },
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = True
            code = run_cli(
                ["--config", str(self.cfg), "--format", "json", "health"], stdout=out
            )

        self.assertEqual(code, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["command"], "health")
        self.assertEqual(payload["data"]["overall_status"], "degraded")
        self.assertIn("services", payload["data"])

    def test_health_command_uses_default_readiness_path(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.health.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.health.check_http_health",
                return_value={"ok": True, "status_code": 200, "error": None},
            ) as checker,
            mock.patch(
                "flowgate.cli.health.comprehensive_health_check",
                return_value={
                    "overall_status": "healthy",
                    "status_counts": {"healthy": 4, "degraded": 0, "unhealthy": 0},
                    "checks": {
                        "disk_space": {
                            "status": "healthy",
                            "message": "OK",
                            "details": {},
                        },
                        "memory": {"status": "healthy", "message": "OK", "details": {}},
                        "credentials": {
                            "status": "healthy",
                            "message": "OK",
                            "details": {},
                        },
                        "port_conflicts": {
                            "status": "healthy",
                            "message": "OK",
                            "details": {},
                        },
                    },
                },
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = True
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)

        self.assertEqual(code, 0)
        checked_urls = [call.args[0] for call in checker.call_args_list]
        self.assertEqual(
            checked_urls, [f"http://127.0.0.1:5000{DEFAULT_READINESS_PATH}"]
        )

    def test_health_command_fails_when_service_not_running(self):
        out = io.StringIO()
        with (
            mock.patch("flowgate.cli.health.ProcessSupervisor") as supervisor_cls,
            mock.patch(
                "flowgate.cli.health.check_http_health",
                return_value={"ok": True, "status_code": 200, "error": None},
            ),
            mock.patch(
                "flowgate.cli.health.comprehensive_health_check",
                return_value={
                    "overall_status": "healthy",
                    "status_counts": {"healthy": 4, "degraded": 0, "unhealthy": 0},
                    "checks": {},
                },
            ),
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = False
            code = run_cli(["--config", str(self.cfg), "health"], stdout=out)
        self.assertEqual(code, 1)
        # New format: service name followed by status
        self.assertIn("cliproxyapi_plus: liveness=fail readiness=ok", out.getvalue())

    def test_service_start_stop_all(self):
        out = io.StringIO()
        out.isatty = lambda: False  # type: ignore[attr-defined]
        with (
            mock.patch(
                "flowgate.cli.service.is_port_available",
                return_value=True,
            ) as port_available,
            mock.patch(
                "flowgate.cli.service.ProcessSupervisor"
            ) as supervisor_cls,
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = False
            supervisor.start.side_effect = [222]
            code = run_cli(
                ["--config", str(self.cfg), "service", "start", "all"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "cliproxyapi_plus:started pid=222")
        port_available.assert_called_once_with("127.0.0.1", 5000)
        supervisor.is_running.assert_called_once_with("cliproxyapi_plus")

        out = io.StringIO()
        with mock.patch(
            "flowgate.cli.service.ProcessSupervisor"
        ) as supervisor_cls:
            supervisor = supervisor_cls.return_value
            supervisor.stop.side_effect = [True]
            code = run_cli(
                ["--config", str(self.cfg), "service", "stop", "all"], stdout=out
            )
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "cliproxyapi_plus:stopped")

    def test_service_start_all_json(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.service.is_port_available",
                return_value=True,
            ) as port_available,
            mock.patch(
                "flowgate.cli.service.ProcessSupervisor"
            ) as supervisor_cls,
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = False
            supervisor.start.side_effect = [222]
            code = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "--format",
                    "json",
                    "service",
                    "start",
                    "all",
                ],
                stdout=out,
            )
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "service.start")
        results = payload["data"]["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["service"], "cliproxyapi_plus")
        port_available.assert_called_once_with("127.0.0.1", 5000)
        supervisor.is_running.assert_called_once_with("cliproxyapi_plus")

    def test_service_start_reports_port_in_use(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.service.is_port_available",
                return_value=False,
            ) as port_available,
            mock.patch(
                "flowgate.cli.service.ProcessSupervisor"
            ) as supervisor_cls,
        ):
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
        port_available.assert_called_once_with("127.0.0.1", 5000)
        supervisor.is_running.assert_called_once_with("cliproxyapi_plus")
        supervisor.start.assert_not_called()

    def test_service_restart_reports_port_in_use_when_service_not_running(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.service.is_port_available",
                return_value=False,
            ) as port_available,
            mock.patch(
                "flowgate.cli.service.ProcessSupervisor"
            ) as supervisor_cls,
        ):
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
        port_available.assert_called_once_with("127.0.0.1", 5000)
        supervisor.is_running.assert_called_once_with("cliproxyapi_plus")
        supervisor.restart.assert_not_called()

    def test_auth_login(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.auth.ProcessSupervisor"
            ) as supervisor_cls,
            mock.patch(
                "flowgate.core.auth.fetch_auth_url",
                return_value="https://example.com/login",
            ) as f_url,
            mock.patch(
                "flowgate.core.auth.poll_auth_status", return_value="success"
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

    def test_auth_login_json(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.auth.ProcessSupervisor"
            ) as supervisor_cls,
            mock.patch(
                "flowgate.core.auth.fetch_auth_url",
                return_value="https://example.com/login",
            ),
            mock.patch("flowgate.core.auth.poll_auth_status", return_value="success"),
        ):
            code = run_cli(
                [
                    "--config",
                    str(self.cfg),
                    "--format",
                    "json",
                    "auth",
                    "login",
                    "codex",
                ],
                stdout=out,
            )
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "auth.login")
        self.assertEqual(payload["data"]["oauth_status"], "success")
        supervisor = supervisor_cls.return_value
        supervisor.record_event.assert_called_once_with(
            "oauth_login", provider="codex", result="success"
        )

    def test_auth_login_timeout_error_contains_hint(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch("flowgate.cli.auth.ProcessSupervisor"),
            mock.patch(
                "flowgate.core.auth.fetch_auth_url",
                return_value="https://example.com/login",
            ),
            mock.patch(
                "flowgate.core.auth.poll_auth_status",
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
            mock.patch(
                "flowgate.cli.auth.ProcessSupervisor"
            ) as supervisor_cls,
            mock.patch(
                "flowgate.core.auth.fetch_auth_url",
                return_value="https://example.com/custom-login",
            ) as f_url,
            mock.patch(
                "flowgate.core.auth.poll_auth_status", return_value="success"
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
            "flowgate.core.auth.get_headless_import_handler", return_value=handler
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
                "flowgate.core.auth.get_headless_import_handler",
                return_value=handler,
            ) as resolver,
            mock.patch(
                "flowgate.cli.auth.ProcessSupervisor"
            ) as supervisor_cls,
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
            "flowgate.core.auth.get_headless_import_handler", return_value=handler
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
        data["paths"]["log_file"] = "../.router/runtime/events.log"
        cfg_path.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        handler = mock.Mock(return_value=Path("/tmp/auths/codex-headless-import.json"))
        with mock.patch(
            "flowgate.core.auth.get_headless_import_handler", return_value=handler
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
        cfg = write_minimal_v3_config(self.root)
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ) as cliproxy_download,
            mock.patch(
                "flowgate.cli.bootstrap.validate_cliproxy_binary",
                return_value=True,
            ) as cliproxy_validate,
        ):
            code = run_cli(["--config", str(cfg), "bootstrap", "download"], stdout=out)
        self.assertEqual(code, 0)
        self.assertIn(
            "cliproxyapi_plus=/tmp/runtime/bin/CLIProxyAPIPlus", out.getvalue()
        )
        self.assertEqual(
            out.getvalue().strip(), "cliproxyapi_plus=/tmp/runtime/bin/CLIProxyAPIPlus"
        )
        cliproxy_download.assert_called_once()
        cliproxy_validate.assert_called_once()

    def test_bootstrap_download_json(self):
        cfg = write_minimal_v3_config(self.root)
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ),
            mock.patch(
                "flowgate.cli.bootstrap.validate_cliproxy_binary",
                return_value=True,
            ),
        ):
            code = run_cli(
                ["--config", str(cfg), "--format", "json", "bootstrap", "download"],
                stdout=out,
            )
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "bootstrap.download")
        self.assertIn("cliproxyapi_plus", payload["data"])
        self.assertEqual(
            set(payload["data"].keys()),
            {"cliproxyapi_plus", "cliproxy_repo", "cliproxy_version"},
        )

    def test_bootstrap_download_rejects_unknown_flag(self):
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["bootstrap", "download", "--unknown-flag", "1.2.3"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_parser_prog_name_is_flowgate(self):
        parser = build_parser()
        self.assertIn("flowgate", parser.format_usage())

    def test_doctor_reports_missing_runtime_artifacts(self):
        cfg = write_minimal_v3_config(self.root)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["paths"]["runtime_dir"] = str(self.root / "missing-runtime")
        cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        code = run_cli(["--config", str(cfg), "doctor"], stdout=out)
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("doctor:cliproxy_config=pass", text)
        self.assertIn("doctor:runtime_dir=fail", text)
        self.assertIn("doctor:runtime_binaries=fail", text)

    def test_doctor_json_reports_missing_runtime_artifacts(self):
        cfg = write_minimal_v3_config(self.root)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["paths"]["runtime_dir"] = str(self.root / "missing-runtime")
        cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        code = run_cli(["--config", str(cfg), "--format", "json", "doctor"], stdout=out)
        self.assertEqual(code, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["command"], "doctor")
        checks = payload["data"]["checks"]
        statuses = {c["id"]: c["status"] for c in checks}
        self.assertEqual(statuses["cliproxy_config"], "pass")
        self.assertEqual(statuses["runtime_dir"], "fail")
        self.assertEqual(statuses["runtime_binaries"], "fail")

    def test_doctor_passes_when_runtime_ready(self):
        cfg = write_minimal_v3_config(self.root)
        data = json.loads(cfg.read_text(encoding="utf-8"))
        secret_dir = self.root / "auths"
        secret_dir.mkdir(parents=True, exist_ok=True)
        secret_file = secret_dir / "codex.json"
        secret_file.write_text("{}", encoding="utf-8")
        os.chmod(secret_file, 0o600)
        data["secret_files"] = [str(secret_file)]
        cfg.write_text(json.dumps(data), encoding="utf-8")

        runtime_bin = self.root / "runtime-v3" / "bin"
        runtime_bin.mkdir(parents=True, exist_ok=True)
        cliproxy = runtime_bin / "CLIProxyAPIPlus"
        cliproxy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cliproxy, 0o755)

        out = io.StringIO()
        code = run_cli(["--config", str(cfg), "doctor"], stdout=out)
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("doctor:cliproxy_config=pass", text)
        self.assertIn("doctor:runtime_dir=pass", text)
        self.assertIn("doctor:runtime_binaries=pass", text)
        self.assertIn("doctor:secret_permissions=pass", text)

    def test_doctor_fails_when_cliproxy_config_missing(self):
        cfg = write_minimal_v3_config(self.root)

        # Ensure runtime is ready so we fail specifically on cliproxy config.
        runtime_bin = self.root / "runtime-v3" / "bin"
        runtime_bin.mkdir(parents=True, exist_ok=True)
        cliproxy_bin = runtime_bin / "CLIProxyAPIPlus"
        cliproxy_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cliproxy_bin, 0o755)

        data = json.loads(cfg.read_text(encoding="utf-8"))
        cliproxy_cfg_path = Path(data["cliproxyapi_plus"]["config_file"])
        cliproxy_cfg_path.unlink()
        cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        code = run_cli(["--config", str(cfg), "doctor"], stdout=out, stderr=err)
        self.assertEqual(code, 2)
        self.assertIn("Configuration file not found", err.getvalue())

    def test_service_start_reports_cliproxyapiplus_update_when_available(self):
        out = TTYStringIO()
        with (
            mock.patch(
                "flowgate.cli.service.ProcessSupervisor"
            ) as supervisor_cls,
            mock.patch(
                "flowgate.core.cliproxyapiplus.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.check_update",
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
        cfg = write_minimal_v3_config(self.root)

        runtime_bin = self.root / "runtime-v3" / "bin"
        runtime_bin.mkdir(parents=True, exist_ok=True)
        cliproxy = runtime_bin / "CLIProxyAPIPlus"
        cliproxy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        os.chmod(cliproxy, 0o755)

        out = TTYStringIO()
        with (
            mock.patch(
                "flowgate.core.cliproxyapiplus.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.check_update",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "https://github.com/router-for-me/CLIProxyAPIPlus/releases/tag/v6.8.18-1",
                },
            ) as checker,
        ):
            code = run_cli(["--config", str(cfg), "doctor"], stdout=out)

        self.assertEqual(code, 0)
        self.assertIn("cliproxyapi_plus:update_available", out.getvalue())
        self.assertIn("latest=v6.8.18-1", out.getvalue())
        checker.assert_called_once()

    def test_auth_login_with_derived_endpoints(self):
        """Test auth login with endpoints derived from cliproxyapi_plus service."""
        # Remove explicit endpoints from config
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        data["auth"]["providers"]["codex"] = {}  # No endpoints
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.auth.ProcessSupervisor"
            ) as supervisor_cls,
            mock.patch(
                "flowgate.core.auth.fetch_auth_url",
                return_value="http://example.local/auth?code=xyz",
            ) as fetch_mock,
            mock.patch(
                "flowgate.core.auth.poll_auth_status",
                return_value="authenticated",
            ) as poll_mock,
        ):
            supervisor = supervisor_cls.return_value
            code = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex"],
                stdout=out,
            )

        self.assertEqual(code, 0)
        # Verify derived endpoints were used
        fetch_mock.assert_called_once()
        poll_mock.assert_called_once()
        # Check that derived URL was used (from cliproxyapi_plus host:port)
        call_args = fetch_mock.call_args
        self.assertIn("127.0.0.1:5000", call_args[0][0])
        self.assertIn("/v0/management/oauth/codex/auth-url", call_args[0][0])

    def test_auth_login_explicit_endpoint_overrides_derived(self):
        """Test that explicit endpoint configuration takes precedence over derived."""
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        # Set explicit endpoint
        data["auth"]["providers"]["codex"] = {
            "auth_url_endpoint": "http://explicit.example.com/auth-url",
            "status_endpoint": "http://explicit.example.com/status",
        }
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.auth.ProcessSupervisor"
            ) as supervisor_cls,
            mock.patch(
                "flowgate.core.auth.fetch_auth_url",
                return_value="http://example.local/auth?code=xyz",
            ) as fetch_mock,
            mock.patch(
                "flowgate.core.auth.poll_auth_status",
                return_value="authenticated",
            ),
        ):
            supervisor = supervisor_cls.return_value
            code = run_cli(
                ["--config", str(self.cfg), "auth", "login", "codex"],
                stdout=out,
            )

        self.assertEqual(code, 0)
        # Verify explicit endpoint was used, not derived
        call_args = fetch_mock.call_args
        self.assertEqual(call_args[0][0], "http://explicit.example.com/auth-url")

    def test_auth_login_fails_when_endpoints_not_derivable(self):
        """Test auth login fails when endpoints cannot be derived."""
        data = json.loads(self.cfg.read_text(encoding="utf-8"))
        # Configure a provider name that FlowGate cannot derive management endpoints for
        data["auth"]["providers"] = {"custom": {}}
        self.cfg.write_text(json.dumps(data), encoding="utf-8")

        out = io.StringIO()
        err = io.StringIO()
        with mock.patch(
            "flowgate.cli.auth.ProcessSupervisor"
        ) as supervisor_cls:
            supervisor = supervisor_cls.return_value
            code = run_cli(
                ["--config", str(self.cfg), "auth", "login", "custom"],
                stdout=out,
                stderr=err,
            )

        self.assertEqual(code, 2)
        self.assertIn("not configured or derivable", err.getvalue())

    def test_bootstrap_update_available_with_yes_flag(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cli.bootstrap._check_latest_version",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "https://github.com/example/releases/tag/v6.8.18-1",
                },
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.validate_cliproxy_binary",
                return_value=True,
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.write_installed_version",
            ) as write_ver,
            mock.patch(
                "flowgate.core.cliproxyapiplus.ProcessSupervisor",
            ) as supervisor_cls,
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = False
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "update", "--yes"],
                stdout=out,
            )

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("cliproxyapi_plus:update_available", text)
        self.assertIn("current=v6.8.16-0", text)
        self.assertIn("latest=v6.8.18-1", text)
        self.assertIn("cliproxyapi_plus:updated version=v6.8.18-1", text)
        write_ver.assert_called_once()

    def test_bootstrap_update_already_up_to_date(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.read_installed_version",
                return_value="v6.8.18-1",
            ),
            mock.patch(
                "flowgate.cli.bootstrap._check_latest_version",
                return_value=None,
            ),
        ):
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "update", "--yes"],
                stdout=out,
            )

        self.assertEqual(code, 0)
        self.assertIn("cliproxyapi_plus:up_to_date", out.getvalue())
        self.assertIn("current=v6.8.18-1", out.getvalue())

    def test_bootstrap_update_auto_restarts_running_service(self):
        out = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cli.bootstrap._check_latest_version",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "",
                },
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.validate_cliproxy_binary",
                return_value=True,
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.write_installed_version",
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.ProcessSupervisor",
            ) as supervisor_cls,
        ):
            supervisor = supervisor_cls.return_value
            supervisor.is_running.return_value = True
            supervisor.restart.return_value = 9999
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "update", "--yes"],
                stdout=out,
            )

        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn("cliproxyapi_plus:restarted pid=9999", text)
        supervisor.is_running.assert_called_once_with("cliproxyapi_plus")
        supervisor.restart.assert_called_once()

    def test_bootstrap_update_requires_yes_in_non_interactive_mode(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cli.bootstrap._check_latest_version",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "",
                },
            ),
            mock.patch(
                "flowgate.cli.bootstrap._confirm_update",
                return_value=False,
            ),
        ):
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "update"],
                stdout=out,
                stderr=err,
            )

        self.assertEqual(code, 2)
        self.assertIn("--yes", err.getvalue())

    def test_bootstrap_update_user_cancels_in_interactive_mode(self):
        out = TTYStringIO()
        with (
            mock.patch("sys.stdin.isatty", return_value=True),
            mock.patch(
                "flowgate.cli.bootstrap.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cli.bootstrap._check_latest_version",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "",
                },
            ),
            mock.patch(
                "flowgate.cli.bootstrap._confirm_update",
                return_value=False,
            ),
        ):
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "update"],
                stdout=out,
            )

        self.assertEqual(code, 0)
        self.assertIn("cliproxyapi_plus:update_cancelled", out.getvalue())

    def test_bootstrap_update_validation_failure_raises(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch(
                "flowgate.cli.bootstrap.read_installed_version",
                return_value="v6.8.16-0",
            ),
            mock.patch(
                "flowgate.cli.bootstrap._check_latest_version",
                return_value={
                    "current_version": "v6.8.16-0",
                    "latest_version": "v6.8.18-1",
                    "release_url": "",
                },
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.download_cliproxyapi_plus",
                return_value=Path("/tmp/runtime/bin/CLIProxyAPIPlus"),
            ),
            mock.patch(
                "flowgate.core.cliproxyapiplus.validate_cliproxy_binary",
                return_value=False,
            ),
        ):
            code = run_cli(
                ["--config", str(self.cfg), "bootstrap", "update", "--yes"],
                stdout=out,
                stderr=err,
            )

        self.assertNotEqual(code, 0)
        self.assertIn("Invalid CLIProxyAPIPlus binary", err.getvalue())


if __name__ == "__main__":
    unittest.main()
