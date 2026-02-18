"""
Profile command handlers for FlowGate CLI.

This module contains command handlers for profile management operations,
including listing available profiles, showing profile details, and switching profiles.
"""
from __future__ import annotations

import sys
from typing import TextIO

from .base import BaseCommand


class ProfileListCommand(BaseCommand):
    """List all available profiles."""

    def execute(self) -> int:
        """Execute profile list command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout

        for name in sorted(self.config["profiles"].keys()):
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

    def execute(self) -> int:
        """Execute profile set command."""
        # Import from cli module for test mocking compatibility
        from ... import cli as cli_module
        from ...profile import activate_profile

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        profile = self.args.name

        try:
            active_path, state_path = activate_profile(self.config, profile)
        except KeyError as exc:
            print(str(exc), file=stderr)
            return 2

        supervisor = cli_module.ProcessSupervisor(self.config["paths"]["runtime_dir"])
        supervisor.record_event("profile_switch", profile=profile, result="success")

        print(f"profile={profile}", file=stdout)
        print(f"active_config={active_path}", file=stdout)
        print(f"state_file={state_path}", file=stdout)

        # If LiteLLM is already running, apply the profile switch immediately by restart.
        if "litellm" in self.config["services"] and supervisor.is_running("litellm"):
            import os

            service = self.config["services"]["litellm"]
            command = service["command"]["args"]
            cwd = service["command"].get("cwd") or os.getcwd()
            pid = supervisor.restart("litellm", command, cwd=cwd)
            print(f"litellm:restarted pid={pid}", file=stdout)
        return 0
