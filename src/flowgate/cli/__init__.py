"""
CLI package for FlowGate.

This package contains the command-line interface implementation,
including argument parsing, command handlers, and CLI utilities.
"""
from __future__ import annotations

import sys
from typing import Any, Iterable, TextIO

from .commands.auth import (
    AuthImportCommand,
    AuthListCommand,
    AuthLoginCommand,
    AuthStatusCommand,
)
from .commands.bootstrap import BootstrapDownloadCommand, BootstrapUpdateCommand
from .commands.health import DoctorCommand, HealthCommand, StatusCommand
from .commands.integration import IntegrationApplyCommand, IntegrationPrintCommand
from .commands.profile import ProfileListCommand, ProfileSetCommand
from .commands.service import (
    ServiceRestartCommand,
    ServiceStartCommand,
    ServiceStopCommand,
)
from .parser import build_parser
from .utils import (
    _load_and_resolve_config,
    _read_state_file,
)

from ..observability import events_log_context, set_events_log_path
from ..config import ConfigError
from ..health import check_http_health
from ..process import ProcessSupervisor
from ..security import check_secret_file_permissions
from ..utils import (
    _is_executable_file,
    _is_service_port_available,
    _runtime_dependency_available,
)

# Backward compatibility alias
_build_parser = build_parser

def run_cli(
    argv: Iterable[str], *, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()

    try:
        args = parser.parse_args(list(argv))

        from pathlib import Path

        cfg_path = Path(args.config).expanduser().resolve()
        early_events_log = cfg_path.parent / ".router" / "runtime" / "events.log"

        with events_log_context(early_events_log):
            config = _load_and_resolve_config(args.config)
            # Prefer resolved config path once available.
            set_events_log_path(config.get("paths", {}).get("log_file"))

            stdout = stdout or sys.stdout
            stderr = stderr or sys.stderr

            # Handle auth command with nested subcommands
            if args.command == "auth":
                args.stdout = stdout
                args.stderr = stderr

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

            if args.command == "profile":
                args.stdout = stdout
                args.stderr = stderr

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
                args.stdout = stdout
                args.stderr = stderr

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
                args.stdout = stdout
                args.stderr = stderr

                bootstrap_command_map = {
                    "download": BootstrapDownloadCommand,
                    "update": BootstrapUpdateCommand,
                }

                bootstrap_cmd = getattr(args, "bootstrap_cmd", None)
                if bootstrap_cmd in bootstrap_command_map:
                    command_class = bootstrap_command_map[bootstrap_cmd]
                    command = command_class(args, config)
                    return command.execute()

            if args.command == "integration":
                args.stdout = stdout
                args.stderr = stderr

                integration_command_map = {
                    "print": IntegrationPrintCommand,
                    "apply": IntegrationApplyCommand,
                }

                integration_cmd = getattr(args, "integration_cmd", None)
                if integration_cmd in integration_command_map:
                    command_class = integration_command_map[integration_cmd]
                    command = command_class(args, config)
                    return command.execute()

            if args.command == "status":
                args.stdout = stdout
                args.stderr = stderr
                return StatusCommand(args, config).execute()

            if args.command == "health":
                args.stdout = stdout
                args.stderr = stderr
                return HealthCommand(args, config).execute()

            if args.command == "doctor":
                args.stdout = stdout
                args.stderr = stderr
                return DoctorCommand(args, config).execute()

            print("Unknown command", file=stderr)
            return 2
    except ConfigError as exc:
        print(f"Config error: {exc}", file=stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Config file not found: {exc}", file=stderr)
        return 2


__all__ = ["run_cli"]
