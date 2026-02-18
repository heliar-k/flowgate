from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Iterable, TextIO

from .cli.commands.auth import (
    AuthImportCommand,
    AuthListCommand,
    AuthLoginCommand,
    AuthStatusCommand,
)
from .cli.commands.bootstrap import BootstrapDownloadCommand
from .cli.commands.health import DoctorCommand, HealthCommand, StatusCommand
from .cli.commands.integration import IntegrationApplyCommand, IntegrationPrintCommand
from .cli.commands.profile import ProfileListCommand, ProfileSetCommand
from .cli.commands.service import (
    ServiceRestartCommand,
    ServiceStartCommand,
    ServiceStopCommand,
)
from .cli.parser import build_parser
from .cli.utils import (
    _load_and_resolve_config,
    _read_state_file,
    _resolve_config_paths,
    _resolve_path,
)
from .config import ConfigError, load_router_config
from .health import check_http_health
from .process import ProcessSupervisor
from .security import check_secret_file_permissions


def _runtime_dependency_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:  # noqa: BLE001
        return False


def _is_service_port_available(host: str, port: int) -> bool:
    """Check if a service port is available for binding."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError:
        return False
    return True


def _upstream_credentials(config: dict[str, Any]) -> dict[str, str]:
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


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


# Command routing map for new command structure
COMMAND_MAP = {
    "status": StatusCommand,
    "health": HealthCommand,
    "doctor": DoctorCommand,
    "auth_list": AuthListCommand,
    "auth_status": AuthStatusCommand,
    "auth_login": AuthLoginCommand,
    "auth_import": AuthImportCommand,
    "profile_list": ProfileListCommand,
    "profile_set": ProfileSetCommand,
    "service_start": ServiceStartCommand,
    "service_stop": ServiceStopCommand,
    "service_restart": ServiceRestartCommand,
    "bootstrap_download": BootstrapDownloadCommand,
    "integration_print": IntegrationPrintCommand,
    "integration_apply": IntegrationApplyCommand,
}


def run_cli(
    argv: Iterable[str], *, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()

    try:
        args = parser.parse_args(list(argv))
        config = _load_and_resolve_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Config file not found: {exc}", file=stderr)
        return 2

    # Route to new command structure if available
    if args.command in COMMAND_MAP:
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr
        command_class = COMMAND_MAP[args.command]
        command = command_class(args, config)
        return command.execute()

    # Handle auth command with nested subcommands
    if args.command == "auth":
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr

        # Map provider to command class
        auth_command_map = {
            "list": AuthListCommand,
            "status": AuthStatusCommand,
            "login": AuthLoginCommand,
            "import-headless": AuthImportCommand,
        }

        provider = getattr(args, "provider", None)
        if provider in auth_command_map:
            command_class = auth_command_map[provider]
            command = command_class(args, config)
            return command.execute()

        # Handle legacy format: auth <provider> <command>
        # e.g., "auth codex login" or "auth codex import-headless"
        auth_cmd = getattr(args, "auth_cmd", None)
        if provider in ("codex", "copilot") and auth_cmd:
            if auth_cmd == "login":
                # Map to new format by setting login_provider
                args.login_provider = provider
                command = AuthLoginCommand(args, config)
                return command.execute()
            if auth_cmd == "import-headless" and provider == "codex":
                # Map to new format by setting import_provider
                args.import_provider = provider
                command = AuthImportCommand(args, config)
                return command.execute()

    if args.command == "profile":
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr

        # Map profile subcommand to command class
        profile_command_map = {
            "list": ProfileListCommand,
            "set": ProfileSetCommand,
        }

        profile_cmd = getattr(args, "profile_cmd", None)
        if profile_cmd in profile_command_map:
            command_class = profile_command_map[profile_cmd]
            command = command_class(args, config)
            return command.execute()

    if args.command == "service":
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr

        # Map service subcommand to command class
        service_command_map = {
            "start": ServiceStartCommand,
            "stop": ServiceStopCommand,
            "restart": ServiceRestartCommand,
        }

        service_cmd = getattr(args, "service_cmd", None)
        if service_cmd in service_command_map:
            command_class = service_command_map[service_cmd]
            command = command_class(args, config)
            return command.execute()

    if args.command == "bootstrap":
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr

        # Map bootstrap subcommand to command class
        bootstrap_command_map = {
            "download": BootstrapDownloadCommand,
        }

        bootstrap_cmd = getattr(args, "bootstrap_cmd", None)
        if bootstrap_cmd in bootstrap_command_map:
            command_class = bootstrap_command_map[bootstrap_cmd]
            command = command_class(args, config)
            return command.execute()

    if args.command == "integration":
        # Inject stdout/stderr into args for command access
        args.stdout = stdout
        args.stderr = stderr

        # Map integration subcommand to command class
        integration_command_map = {
            "print": IntegrationPrintCommand,
            "apply": IntegrationApplyCommand,
        }

        integration_cmd = getattr(args, "integration_cmd", None)
        if integration_cmd in integration_command_map:
            command_class = integration_command_map[integration_cmd]
            command = command_class(args, config)
            return command.execute()

    print("Unknown command", file=stderr)
    return 2
