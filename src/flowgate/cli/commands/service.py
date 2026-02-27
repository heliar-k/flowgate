"""
Service lifecycle command handlers for FlowGate CLI.

This module contains command handlers for starting, stopping, and restarting services.
"""
from __future__ import annotations

import os
import sys
from typing import Any, TextIO

from ...constants import CLIPROXYAPI_PLUS_SERVICE, DEFAULT_SERVICE_HOST
from ...config import ConfigError
from ...process import ProcessSupervisor
from ...utils import _is_service_port_available
from ..error_handler import handle_command_errors
from ..output import Output, command_id_from_args
from .base import BaseCommand


def _service_names(config: dict[str, Any], target: str) -> list[str]:
    """Resolve service names from target (service name or 'all')."""
    if target == "all":
        return list(config["services"].keys())
    if target not in config["services"]:
        raise ConfigError(f"Unknown service: {target}")
    return [target]


def _maybe_print_cliproxyapiplus_update(
    config: dict[str, Any], *, stdout: TextIO
) -> None:
    """Print CLIProxyAPIPlus update notification if available."""
    from ...bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION
    from ...cliproxyapiplus_update_check import (
        check_cliproxyapiplus_update,
        read_cliproxyapiplus_installed_version,
    )

    isatty = getattr(stdout, "isatty", None)
    if callable(isatty) and not isatty():
        return

    runtime_dir = str(config.get("paths", {}).get("runtime_dir", "")).strip()
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
        config.get("_meta", {}).get("config_path", "config/flowgate.yaml")
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
            f"bootstrap update'"
        ),
        file=stdout,
    )


class ServiceStartCommand(BaseCommand):
    """Start one or all services."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute service start command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        supervisor = ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        target = self.args.target

        names = _service_names(self.config, target)

        ok = True
        started_cliproxy = False
        results: list[dict[str, Any]] = []

        for name in names:
            service = self.config["services"][name]
            args = service["command"]["args"]
            cwd = service["command"].get("cwd")
            host = str(service.get("host", DEFAULT_SERVICE_HOST))
            port = service.get("port")
            if cwd is None:
                cwd = os.getcwd()

            # Check port availability before starting
            if isinstance(port, int):
                running = supervisor.is_running(name)
                if not running and not _is_service_port_available(host, port):
                    ok = False
                    results.append(
                        {
                            "service": name,
                            "action": "start",
                            "ok": False,
                            "reason": "port-in-use",
                            "host": host,
                            "port": port,
                        }
                    )
                    if output.format == "legacy":
                        print(
                            f"{name}:start-failed reason=port-in-use host={host} port={port}",
                            file=stderr,
                        )
                    continue

            pid = supervisor.start(name, args, cwd=cwd)
            results.append(
                {
                    "service": name,
                    "action": "start",
                    "ok": True,
                    "pid": pid,
                    "host": host,
                    "port": port,
                }
            )
            if output.format == "legacy":
                print(f"{name}:started pid={pid}", file=stdout)
            if name == CLIPROXYAPI_PLUS_SERVICE:
                started_cliproxy = True

        if output.format == "legacy" and started_cliproxy:
            _maybe_print_cliproxyapiplus_update(self.config, stdout=stdout)

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": bool(ok),
                    "command": command_id_from_args(self.args),
                    "data": {"results": results},
                    "warnings": [],
                    "errors": [],
                }
            )
        return 0 if ok else 1


class ServiceStopCommand(BaseCommand):
    """Stop one or all services."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute service stop command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        supervisor = ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        target = self.args.target

        names = _service_names(self.config, target)

        ok = True
        results: list[dict[str, Any]] = []
        for name in names:
            stopped = supervisor.stop(name)
            results.append(
                {
                    "service": name,
                    "action": "stop",
                    "ok": bool(stopped),
                }
            )
            if output.format == "legacy":
                print(
                    f"{name}:{'stopped' if stopped else 'stop-failed'}",
                    file=stdout,
                )
            ok = ok and stopped

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": bool(ok),
                    "command": command_id_from_args(self.args),
                    "data": {"results": results},
                    "warnings": [],
                    "errors": [],
                }
            )
        return 0 if ok else 1


class ServiceRestartCommand(BaseCommand):
    """Restart one or all services."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute service restart command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        supervisor = ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        target = self.args.target

        names = _service_names(self.config, target)

        ok = True
        results: list[dict[str, Any]] = []
        for name in names:
            service = self.config["services"][name]
            args = service["command"]["args"]
            cwd = service["command"].get("cwd")
            host = str(service.get("host", DEFAULT_SERVICE_HOST))
            port = service.get("port")
            if cwd is None:
                cwd = os.getcwd()

            # Check port availability if service is not currently running
            if isinstance(port, int):
                running = supervisor.is_running(name)
                if not running and not _is_service_port_available(host, port):
                    ok = False
                    results.append(
                        {
                            "service": name,
                            "action": "restart",
                            "ok": False,
                            "reason": "port-in-use",
                            "host": host,
                            "port": port,
                        }
                    )
                    if output.format == "legacy":
                        print(
                            f"{name}:restart-failed reason=port-in-use host={host} port={port}",
                            file=stderr,
                        )
                    continue

            pid = supervisor.restart(name, args, cwd=cwd)
            results.append(
                {
                    "service": name,
                    "action": "restart",
                    "ok": True,
                    "pid": pid,
                    "host": host,
                    "port": port,
                }
            )
            if output.format == "legacy":
                print(f"{name}:restarted pid={pid}", file=stdout)

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": bool(ok),
                    "command": command_id_from_args(self.args),
                    "data": {"results": results},
                    "warnings": [],
                    "errors": [],
                }
            )
        return 0 if ok else 1
