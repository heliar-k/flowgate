"""
Health and diagnostic command handlers for FlowGate CLI.

This module contains command handlers for health checks, doctor diagnostics,
and status reporting.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, TextIO

from ...constants import DEFAULT_READINESS_PATH, DEFAULT_SERVICE_HOST
from ...security import check_secret_file_permissions
from ..error_handler import handle_command_errors
from ..utils import _read_state_file
from .base import BaseCommand


def _effective_secret_files(config: dict[str, Any]) -> list[str]:
    """Collect all secret files from config and auth directory."""
    from ..utils import _default_auth_dir

    paths: set[str] = set()
    for value in config.get("secret_files", []):
        if isinstance(value, str) and value.strip():
            paths.add(str(Path(value).resolve()))

    default_auth_dir = Path(_default_auth_dir(config))
    if default_auth_dir.exists():
        for item in default_auth_dir.glob("*.json"):
            paths.add(str(item.resolve()))

    return sorted(paths)


def _upstream_credentials(config: dict[str, Any]) -> dict[str, str]:
    """Extract upstream credential file paths from config."""
    credentials = config.get("credentials", {})
    if not isinstance(credentials, dict):
        return {}

    upstream = credentials.get("upstream", {})
    if not isinstance(upstream, dict):
        return {}

    result: dict[str, str] = {}
    for name, entry in upstream.items():
        if not isinstance(name, str):
            continue
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file")
        if isinstance(file_path, str) and file_path.strip():
            result[name] = file_path
    return result


def _collect_api_key_refs(litellm_config: Any) -> set[str]:
    """Collect all api_key_ref values from litellm config."""
    refs: set[str] = set()
    if not isinstance(litellm_config, dict):
        return refs

    model_list = litellm_config.get("model_list")
    if not isinstance(model_list, list):
        return refs

    for item in model_list:
        if not isinstance(item, dict):
            continue
        params = item.get("litellm_params")
        if not isinstance(params, dict):
            continue
        ref = params.get("api_key_ref")
        if isinstance(ref, str) and ref.strip():
            refs.add(ref.strip())
    return refs


def _upstream_credential_issues(config: dict[str, Any]) -> list[str]:
    """Check for issues with upstream credential files."""
    refs = _collect_api_key_refs(config.get("litellm_base", {}))
    profiles = config.get("profiles", {})
    if isinstance(profiles, dict):
        for overlay in profiles.values():
            refs.update(_collect_api_key_refs(overlay))

    if not refs:
        return []

    upstream = _upstream_credentials(config)
    issues: list[str] = []
    for ref in sorted(refs):
        file_path = upstream.get(ref)
        if not file_path:
            issues.append(f"missing-ref:{ref}")
            continue

        key_path = Path(file_path)
        if not key_path.exists():
            issues.append(f"missing-file:{ref}:{key_path}")
            continue
        if not key_path.is_file():
            issues.append(f"not-a-file:{ref}:{key_path}")
            continue
        try:
            api_key = key_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            issues.append(f"read-error:{ref}:{type(exc).__name__}")
            continue
        if not api_key:
            issues.append(f"empty-file:{ref}:{key_path}")
            continue

    return issues


class StatusCommand(BaseCommand):
    """Display current profile and service status."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute status command."""
        # Import from cli module for test mocking compatibility
        from ... import cli as cli_module

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout

        state = _read_state_file(Path(self.config["paths"]["state_file"]))
        profile = state.get("current_profile", "unknown")
        updated_at = state.get("updated_at", "unknown")

        print(f"current_profile={profile}", file=stdout)
        print(f"updated_at={updated_at}", file=stdout)

        supervisor = cli_module.ProcessSupervisor(self.config["paths"]["runtime_dir"])
        for name in sorted(self.config["services"].keys()):
            running = supervisor.is_running(name)
            print(f"{name}_running={'yes' if running else 'no'}", file=stdout)

        issues = check_secret_file_permissions(_effective_secret_files(self.config))
        if issues:
            print(f"secret_permission_issues={len(issues)}", file=stdout)
        else:
            print("secret_permission_issues=0", file=stdout)

        return 0


class HealthCommand(BaseCommand):
    """Check liveness and readiness of all services."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute health command."""
        # Import from cli module for test mocking compatibility
        from ... import cli as cli_module

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout

        supervisor = cli_module.ProcessSupervisor(self.config["paths"]["runtime_dir"])
        all_ok = True
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
            code = readiness["status_code"]
            error = readiness["error"]
            print(
                (
                    f"{name}:liveness={'ok' if liveness_ok else 'fail'} "
                    f"readiness={'ok' if readiness_ok else 'fail'} "
                    f"running={'yes' if running else 'no'} "
                    f"readiness_code={code if code is not None else 'n/a'} "
                    f"readiness_error={error or 'none'} "
                    f"readiness_url={readiness_url}"
                ),
                file=stdout,
            )

            all_ok = all_ok and liveness_ok and readiness_ok
        return 0 if all_ok else 1


class DoctorCommand(BaseCommand):
    """Run comprehensive diagnostic checks."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute doctor command."""
        # Import helper functions from cli module for test mocking compatibility
        from ... import cli as cli_module

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        all_ok = True

        config_path = self.config.get("_meta", {}).get("config_path", "unknown")
        print(f"doctor:config=pass path={config_path}", file=stdout)

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
            "litellm": runtime_bin / "litellm",
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

        issues = check_secret_file_permissions(_effective_secret_files(self.config))
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

        upstream_issues = _upstream_credential_issues(self.config)
        if upstream_issues:
            all_ok = False
            print(
                "doctor:upstream_credentials=fail "
                f"issues={len(upstream_issues)} "
                "suggestion='define credentials.upstream entries and ensure each api_key_ref file exists with non-empty content'",
                file=stdout,
            )
        else:
            print("doctor:upstream_credentials=pass issues=0", file=stdout)

        if cli_module._runtime_dependency_available("litellm"):
            print("doctor:runtime_dependency=pass module=litellm", file=stdout)
        else:
            all_ok = False
            print(
                "doctor:runtime_dependency=fail " "module=litellm " "suggestion='uv sync'",
                file=stdout,
            )

        # Check for CLIProxyAPIPlus updates (only if stdout is a tty)
        self._maybe_print_cliproxyapiplus_update(stdout)

        return 0 if all_ok else 1

    def _maybe_print_cliproxyapiplus_update(self, stdout: TextIO) -> None:
        """Print CLIProxyAPIPlus update notification if available."""
        from ...bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION
        from ...cliproxyapiplus_update_check import (
            check_cliproxyapiplus_update,
            read_cliproxyapiplus_installed_version,
        )

        isatty = getattr(stdout, "isatty", None)
        if callable(isatty) and not isatty():
            return

        runtime_dir = str(self.config.get("paths", {}).get("runtime_dir", "")).strip()
        if not runtime_dir:
            return

        current_version = read_cliproxyapiplus_installed_version(
            runtime_dir, DEFAULT_CLIPROXY_VERSION
        )
        update = check_cliproxyapiplus_update(
            runtime_dir=runtime_dir,
            current_version=current_version,
            repo=DEFAULT_CLIPROXY_REPO,
        )
        if not update:
            return

        latest = update["latest_version"]
        release_url = update.get("release_url", "")
        config_path = str(
            self.config.get("_meta", {}).get("config_path", "config/flowgate.yaml")
        )
        print(
            (
                "cliproxyapi_plus:update_available "
                f"current={current_version} latest={latest} "
                f"release={release_url if release_url else 'n/a'}"
            ),
            file=stdout,
        )
        print(
            (
                "cliproxyapi_plus:update_suggestion "
                "command="
                f"'uv run flowgate --config {config_path} "
                f"bootstrap download --cliproxy-version {latest}'"
            ),
            file=stdout,
        )
