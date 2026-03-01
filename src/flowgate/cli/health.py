"""
Health and diagnostic command handlers for FlowGate CLI.

This module contains command handlers for health checks, doctor diagnostics,
and status reporting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

from ..constants import DEFAULT_READINESS_PATH, DEFAULT_SERVICE_HOST
from ..security import check_secret_file_permissions
from .error_handler import handle_command_errors
from .helpers import effective_secret_files, maybe_print_update_notification
from .output import Output, command_id_from_args
from .base import BaseCommand


class StatusCommand(BaseCommand):
    """Display service status."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute status command."""
        # Import from cli module for test mocking compatibility
        from .. import cli as cli_module

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        supervisor = cli_module.ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        services: dict[str, bool] = {}
        for name in sorted(self.config["services"].keys()):
            services[name] = bool(supervisor.is_running(name))

        issues = check_secret_file_permissions(effective_secret_files(self.config))
        secret_issue_count = len(issues)

        cliproxy_cfg = None
        cliproxy_section = self.config.get("cliproxyapi_plus", {})
        if isinstance(cliproxy_section, dict):
            cliproxy_cfg = cliproxy_section.get("config_file")
        cliproxy_cfg_str = str(cliproxy_cfg).strip() if cliproxy_cfg else ""

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "services": services,
                        "cliproxyapi_plus_config": cliproxy_cfg_str,
                        "secret_permission_issues": secret_issue_count,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        for name in sorted(services.keys()):
            print(
                f"services.{name}_running={'yes' if services[name] else 'no'}",
                file=stdout,
            )
        if cliproxy_cfg_str:
            print(f"cliproxyapi_plus_config={cliproxy_cfg_str}", file=stdout)
        print(f"secret_permission_issues={secret_issue_count}", file=stdout)

        return 0


class HealthCommand(BaseCommand):
    """Check liveness and readiness of all services."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute health command."""
        # Import from cli module for test mocking compatibility
        from .. import cli as cli_module
        from ..health import comprehensive_health_check

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )
        verbose = getattr(self.args, "verbose", False)

        # Run comprehensive health check
        health_result = comprehensive_health_check(self.config, verbose=verbose)

        # Print overall status
        overall = health_result["overall_status"]
        counts = health_result["status_counts"]
        if output.format == "legacy":
            ok_icon = "✓" if not output.plain else "+"
            warn_icon = "⚠" if not output.plain else "!"
            bad_icon = "✗" if not output.plain else "x"
            print(
                f"Overall Status: {overall.upper()} "
                f"({ok_icon} {counts['healthy']} healthy, "
                f"{warn_icon} {counts['degraded']} degraded, "
                f"{bad_icon} {counts['unhealthy']} unhealthy)",
                file=stdout,
            )
            print("", file=stdout)

        # Print individual check results
        checks = health_result["checks"]
        if output.format == "legacy":
            for check_name, result in checks.items():
                status = result["status"]
                message = result["message"]

                # Status icon
                if status == "healthy":
                    icon = "✓"
                elif status == "degraded":
                    icon = "⚠"
                else:
                    icon = "✗"

                if output.plain:
                    icon = {"✓": "+", "⚠": "!", "✗": "x"}.get(icon, icon)

                print(f"{icon} {check_name}: {message}", file=stdout)

                # Print details in verbose mode
                if verbose and result.get("details"):
                    details = result["details"]
                    for key, value in details.items():
                        if isinstance(value, (list, dict)) and value:
                            print(f"  {key}: {value}", file=stdout)
                        elif not isinstance(value, (list, dict)):
                            print(f"  {key}: {value}", file=stdout)

            print("", file=stdout)

        # Also run service health checks
        supervisor = cli_module.ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        all_ok = overall == "healthy"

        if output.format == "legacy":
            print("Service Health:", file=stdout)
        service_results: list[dict[str, Any]] = []
        for name, service in sorted(self.config["services"].items()):
            running = supervisor.is_running(name)
            liveness_ok = running

            host = service.get("host", DEFAULT_SERVICE_HOST)
            port = service.get("port")
            readiness_path = (
                service.get("readiness_path")
                or service.get("health_path")
                or DEFAULT_READINESS_PATH
            )

            if isinstance(port, int):
                readiness_url = f"http://{host}:{port}{readiness_path}"
                readiness = cli_module.check_http_health(readiness_url, timeout=1.0)
            else:
                readiness_url = "n/a"
                readiness = {"ok": False, "status_code": None, "error": "missing-port"}

            readiness_ok = bool(readiness["ok"])
            service_results.append(
                {
                    "name": name,
                    "running": bool(running),
                    "liveness_ok": bool(liveness_ok),
                    "readiness_ok": bool(readiness_ok),
                    "readiness_url": readiness_url,
                    "readiness_code": readiness.get("status_code"),
                    "readiness_error": readiness.get("error"),
                }
            )

            # Status icon
            if liveness_ok and readiness_ok:
                icon = "✓"
            else:
                icon = "✗"

            if output.format == "legacy":
                if output.plain:
                    icon = "+" if icon == "✓" else "x"
                print(
                    f"{icon} {name}: "
                    f"liveness={'ok' if liveness_ok else 'fail'} "
                    f"readiness={'ok' if readiness_ok else 'fail'}",
                    file=stdout,
                )

                if verbose:
                    code = readiness["status_code"]
                    error = readiness["error"]
                    print(f"  running: {'yes' if running else 'no'}", file=stdout)
                    print(f"  readiness_url: {readiness_url}", file=stdout)
                    if code is not None:
                        print(f"  readiness_code: {code}", file=stdout)
                    if error:
                        print(f"  readiness_error: {error}", file=stdout)

            all_ok = all_ok and liveness_ok and readiness_ok

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": bool(all_ok),
                    "command": command_id_from_args(self.args),
                    "data": {
                        "overall_status": overall,
                        "status_counts": counts,
                        "checks": checks,
                        "services": service_results,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
        return 0 if all_ok else 1


class DoctorCommand(BaseCommand):
    """Run comprehensive diagnostic checks."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute doctor command."""
        # Import helper functions from cli module for test mocking compatibility
        from .. import cli as cli_module

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        if output.format != "legacy":
            all_ok = True
            checks_out: list[dict[str, Any]] = []

            config_path = self.config.get("_meta", {}).get("config_path", "unknown")
            checks_out.append(
                {"id": "config", "status": "pass", "path": str(config_path)}
            )

            cliproxy_cfg_raw = self.config.get("cliproxyapi_plus", {}) or {}
            cliproxy_cfg_value = (
                cliproxy_cfg_raw.get("config_file")
                if isinstance(cliproxy_cfg_raw, dict)
                else None
            )
            cliproxy_cfg_str = (
                str(cliproxy_cfg_value).strip() if cliproxy_cfg_value else ""
            )
            cliproxy_cfg_path = Path(cliproxy_cfg_str) if cliproxy_cfg_str else None
            cliproxy_suggestion = (
                "copy config/examples/cliproxyapi.yaml to config/cliproxyapi.yaml"
            )
            if cliproxy_cfg_path is None:
                all_ok = False
                checks_out.append(
                    {
                        "id": "cliproxy_config",
                        "status": "fail",
                        "path": "",
                        "suggestion": cliproxy_suggestion,
                    }
                )
            elif not cliproxy_cfg_path.exists():
                all_ok = False
                checks_out.append(
                    {
                        "id": "cliproxy_config",
                        "status": "fail",
                        "path": str(cliproxy_cfg_path),
                        "suggestion": cliproxy_suggestion,
                    }
                )
            else:
                try:
                    text = cliproxy_cfg_path.read_text(encoding="utf-8")
                    try:
                        import yaml  # type: ignore

                        loaded = yaml.safe_load(text)
                    except ModuleNotFoundError:
                        loaded = json.loads(text)
                    is_mapping = isinstance(loaded, dict)
                except Exception:  # noqa: BLE001
                    is_mapping = False
                if is_mapping:
                    checks_out.append(
                        {
                            "id": "cliproxy_config",
                            "status": "pass",
                            "path": str(cliproxy_cfg_path),
                        }
                    )
                else:
                    all_ok = False
                    checks_out.append(
                        {
                            "id": "cliproxy_config",
                            "status": "fail",
                            "path": str(cliproxy_cfg_path),
                            "suggestion": cliproxy_suggestion,
                        }
                    )

            runtime_dir = Path(self.config["paths"]["runtime_dir"])
            if runtime_dir.exists():
                checks_out.append(
                    {"id": "runtime_dir", "status": "pass", "path": str(runtime_dir)}
                )
            else:
                all_ok = False
                checks_out.append(
                    {
                        "id": "runtime_dir",
                        "status": "fail",
                        "path": str(runtime_dir),
                        "suggestion": "run bootstrap download to create runtime artifacts",
                    }
                )

            runtime_bin = runtime_dir / "bin"
            required_bins = {
                "CLIProxyAPIPlus": runtime_bin / "CLIProxyAPIPlus",
            }
            missing_or_non_exec = [
                name
                for name, binary_path in required_bins.items()
                if not cli_module._is_executable_file(binary_path)
            ]
            if missing_or_non_exec:
                all_ok = False
                checks_out.append(
                    {
                        "id": "runtime_binaries",
                        "status": "fail",
                        "path": str(runtime_bin),
                        "missing": missing_or_non_exec,
                        "suggestion": "uv run flowgate --config config/flowgate.yaml bootstrap download",
                    }
                )
            else:
                checks_out.append(
                    {
                        "id": "runtime_binaries",
                        "status": "pass",
                        "path": str(runtime_bin),
                    }
                )

            issues = check_secret_file_permissions(effective_secret_files(self.config))
            if issues:
                all_ok = False
                checks_out.append(
                    {
                        "id": "secret_permissions",
                        "status": "fail",
                        "issues": len(issues),
                        "suggestion": "chmod 600 <secret-file>",
                    }
                )
            else:
                checks_out.append(
                    {"id": "secret_permissions", "status": "pass", "issues": 0}
                )

            output.emit_envelope(
                {
                    "ok": bool(all_ok),
                    "command": command_id_from_args(self.args),
                    "data": {"checks": checks_out},
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0 if all_ok else 1

        all_ok = True

        config_path = self.config.get("_meta", {}).get("config_path", "unknown")
        print(f"doctor:config=pass path={config_path}", file=stdout)

        cliproxy_cfg_raw = self.config.get("cliproxyapi_plus", {}) or {}
        cliproxy_cfg_value = (
            cliproxy_cfg_raw.get("config_file")
            if isinstance(cliproxy_cfg_raw, dict)
            else None
        )
        cliproxy_cfg_str = str(cliproxy_cfg_value).strip() if cliproxy_cfg_value else ""
        cliproxy_cfg_path = Path(cliproxy_cfg_str) if cliproxy_cfg_str else None
        cliproxy_suggestion = (
            "copy config/examples/cliproxyapi.yaml to config/cliproxyapi.yaml"
        )
        if cliproxy_cfg_path is None:
            all_ok = False
            print(
                f"doctor:cliproxy_config=fail path= suggestion='{cliproxy_suggestion}'",
                file=stdout,
            )
        elif not cliproxy_cfg_path.exists():
            all_ok = False
            print(
                "doctor:cliproxy_config=fail "
                f"path={cliproxy_cfg_path} "
                f"suggestion='{cliproxy_suggestion}'",
                file=stdout,
            )
        else:
            try:
                text = cliproxy_cfg_path.read_text(encoding="utf-8")
                try:
                    import yaml  # type: ignore

                    loaded = yaml.safe_load(text)
                except ModuleNotFoundError:
                    loaded = json.loads(text)
                ok = isinstance(loaded, dict)
            except Exception:  # noqa: BLE001
                ok = False

            if ok:
                print(
                    f"doctor:cliproxy_config=pass path={cliproxy_cfg_path}",
                    file=stdout,
                )
            else:
                all_ok = False
                print(
                    "doctor:cliproxy_config=fail "
                    f"path={cliproxy_cfg_path} "
                    f"suggestion='{cliproxy_suggestion}'",
                    file=stdout,
                )

        runtime_dir = Path(self.config["paths"]["runtime_dir"])
        if runtime_dir.exists():
            print(f"doctor:runtime_dir=pass path={runtime_dir}", file=stdout)
        else:
            all_ok = False
            print(
                "doctor:runtime_dir=fail "
                f"path={runtime_dir} "
                "suggestion='run bootstrap download to create runtime artifacts'",
                file=stdout,
            )

        runtime_bin = runtime_dir / "bin"
        required_bins = {
            "CLIProxyAPIPlus": runtime_bin / "CLIProxyAPIPlus",
        }
        missing_or_non_exec = [
            name
            for name, binary_path in required_bins.items()
            if not cli_module._is_executable_file(binary_path)
        ]
        if missing_or_non_exec:
            all_ok = False
            print(
                "doctor:runtime_binaries=fail "
                f"missing={','.join(missing_or_non_exec)} "
                "suggestion='uv run flowgate --config config/flowgate.yaml bootstrap download'",
                file=stdout,
            )
        else:
            print(f"doctor:runtime_binaries=pass path={runtime_bin}", file=stdout)

        issues = check_secret_file_permissions(effective_secret_files(self.config))
        if issues:
            all_ok = False
            print(
                "doctor:secret_permissions=fail "
                f"issues={len(issues)} "
                "suggestion='chmod 600 <secret-file>'",
                file=stdout,
            )
        else:
            print("doctor:secret_permissions=pass issues=0", file=stdout)

        # Check for CLIProxyAPIPlus updates (only if stdout is a tty)
        maybe_print_update_notification(self.config, stdout=stdout)

        return 0 if all_ok else 1
