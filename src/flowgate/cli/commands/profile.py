"""
Profile command handlers for FlowGate CLI.

This module contains command handlers for profile management operations,
including listing available profiles, showing profile details, and switching profiles.
"""
from __future__ import annotations

import sys
from typing import TextIO

from ..error_handler import handle_command_errors
from ..output import Output, command_id_from_args
from .base import BaseCommand


class ProfileListCommand(BaseCommand):
    """List all available profiles."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute profile list command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        names = sorted(self.config["profiles"].keys())
        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {"profiles": names},
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        for name in names:
            print(name, file=stdout)
        return 0


class ProfileShowCommand(BaseCommand):
    """Show details of a specific profile."""

    def execute(self) -> int:
        """Execute profile show command."""
        # This command is not yet implemented in the original CLI
        # Placeholder for future implementation
        raise NotImplementedError("profile show command not yet implemented")


class ProfileSetCommand(BaseCommand):
    """Set the active profile."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute profile set command."""
        # Import from cli module for test mocking compatibility
        from ... import cli as cli_module
        from ...profile import activate_profile

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        profile = self.args.name

        try:
            active_path, state_path = activate_profile(self.config, profile)
        except KeyError as exc:
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(self.args),
                        "data": {"profile": profile},
                        "warnings": [],
                        "errors": [{"type": "ConfigError", "message": str(exc)}],
                    }
                )
            print(str(exc), file=stderr)
            return 2

        supervisor = cli_module.ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        supervisor.record_event("profile_switch", profile=profile, result="success")

        restarted_pid: int | None = None

        # If LiteLLM is already running, apply the profile switch immediately by restart.
        if "litellm" in self.config["services"] and supervisor.is_running("litellm"):
            import os

            service = self.config["services"]["litellm"]
            command = service["command"]["args"]
            cwd = service["command"].get("cwd") or os.getcwd()
            pid = supervisor.restart("litellm", command, cwd=cwd)
            restarted_pid = int(pid)

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "profile": profile,
                        "active_config": active_path,
                        "state_file": state_path,
                        "litellm_restarted_pid": restarted_pid,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        print(f"profile={profile}", file=stdout)
        print(f"active_config={active_path}", file=stdout)
        print(f"state_file={state_path}", file=stdout)
        if restarted_pid is not None:
            print(f"litellm:restarted pid={restarted_pid}", file=stdout)
        return 0
