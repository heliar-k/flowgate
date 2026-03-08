"""
CLI package for FlowGate.

This package contains the command-line interface implementation,
including argument parsing, command handlers, and CLI utilities.
"""

from __future__ import annotations

import logging
import sys
import traceback
from collections.abc import Iterable
from typing import Any, TextIO

from flowgate.core.config import ConfigError
from flowgate.core.observability import events_log_context, set_events_log_path
from flowgate.cli.auth import (
    AuthImportCommand,
    AuthListCommand,
    AuthLoginCommand,
    AuthStatusCommand,
)
from flowgate.cli.bootstrap import BootstrapDownloadCommand, BootstrapUpdateCommand
from flowgate.cli.error_handler import EXIT_CONFIG_ERROR, EXIT_RUNTIME_ERROR
from flowgate.cli.health import DoctorCommand, HealthCommand, StatusCommand
from flowgate.cli.helpers import (
    _load_and_resolve_config,
)
from flowgate.cli.output import Output
from flowgate.cli.parser import build_parser
from flowgate.cli.service import (
    ServiceRestartCommand,
    ServiceStartCommand,
    ServiceStopCommand,
)


def run_cli(
    argv: Iterable[str], *, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()

    try:
        args = parser.parse_args(list(argv))
        if getattr(args, "debug", False):
            logging.basicConfig(level=logging.DEBUG)
        args.stdout = stdout
        args.stderr = stderr
        args._output = Output.from_args(args, stdout=stdout, stderr=stderr)

        from pathlib import Path

        cfg_path = Path(args.config).expanduser().resolve()
        early_events_log = cfg_path.parent / ".router" / "runtime" / "events.log"

        with events_log_context(early_events_log):
            config = _load_and_resolve_config(args.config)
            # Prefer resolved config path once available.
            set_events_log_path(config.get("paths", {}).get("log_file"))

            stdout = stdout or sys.stdout
            stderr = stderr or sys.stderr
            args.stdout = stdout
            args.stderr = stderr
            args._output = Output.from_args(args, stdout=stdout, stderr=stderr)

            # Handle auth command with nested subcommands
            if args.command == "auth":
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

            if args.command == "service":
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
                bootstrap_command_map = {
                    "download": BootstrapDownloadCommand,
                    "update": BootstrapUpdateCommand,
                }

                bootstrap_cmd = getattr(args, "bootstrap_cmd", None)
                if bootstrap_cmd in bootstrap_command_map:
                    command_class = bootstrap_command_map[bootstrap_cmd]
                    command = command_class(args, config)
                    return command.execute()

            if args.command == "status":
                return StatusCommand(args, config).execute()

            if args.command == "health":
                return HealthCommand(args, config).execute()

            if args.command == "doctor":
                return DoctorCommand(args, config).execute()

            print("Unknown command", file=stderr)
            return EXIT_CONFIG_ERROR
    except ConfigError as exc:
        fmt = "legacy"
        if "args" in locals():
            fmt = str(getattr(args, "_output").format)
        if fmt != "legacy" and "args" in locals():
            getattr(args, "_output").emit_envelope(
                {
                    "ok": False,
                    "command": "config",
                    "data": {},
                    "warnings": [],
                    "errors": [{"type": "ConfigError", "message": str(exc)}],
                }
            )
        print(f"❌ Configuration error: {exc}", file=stderr)
        if "args" in locals() and getattr(args, "debug", False):
            traceback.print_exc(file=stderr)
        return EXIT_CONFIG_ERROR
    except FileNotFoundError as exc:
        fmt = "legacy"
        if "args" in locals():
            fmt = str(getattr(args, "_output").format)
        if fmt != "legacy" and "args" in locals():
            getattr(args, "_output").emit_envelope(
                {
                    "ok": False,
                    "command": "config",
                    "data": {},
                    "warnings": [],
                    "errors": [{"type": "FileNotFoundError", "message": str(exc)}],
                }
            )
        print(f"❌ Configuration file not found: {exc}", file=stderr)
        if "args" in locals() and getattr(args, "debug", False):
            traceback.print_exc(file=stderr)
        return EXIT_CONFIG_ERROR
    except Exception as exc:
        fmt = "legacy"
        if "args" in locals():
            fmt = str(getattr(args, "_output").format)
        if fmt != "legacy" and "args" in locals():
            getattr(args, "_output").emit_envelope(
                {
                    "ok": False,
                    "command": "internal",
                    "data": {},
                    "warnings": [],
                    "errors": [{"type": type(exc).__name__, "message": str(exc)}],
                }
            )
        print(f"❌ Internal error: {exc}", file=stderr)
        if "args" in locals() and getattr(args, "debug", False):
            traceback.print_exc(file=stderr)
        else:
            print("Re-run with --debug for a stack trace.", file=stderr)
        return EXIT_RUNTIME_ERROR


__all__ = ["run_cli"]
