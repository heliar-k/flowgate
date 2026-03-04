"""
Bootstrap command handlers for FlowGate CLI.

This module contains command handlers for downloading and setting up
runtime dependencies (CLIProxyAPIPlus binary).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from ..core.bootstrap import (
    DEFAULT_CLIPROXY_VERSION,
    download_cliproxyapi_plus,
    validate_cliproxy_binary,
)
from ..core.cliproxyapiplus import (
    check_latest_version,
    perform_update,
    read_installed_version,
    write_installed_version,
)
from ..core.constants import CLIPROXYAPI_PLUS_SERVICE
from .base import BaseCommand
from .error_handler import handle_command_errors
from .output import Output, command_id_from_args


class BootstrapDownloadCommand(BaseCommand):
    """Download and prepare runtime binaries (CLIProxyAPIPlus)."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute bootstrap download command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        runtime_bin_dir = Path(self.config["paths"]["runtime_dir"]) / "bin"
        cliproxy_version = self.args.cliproxy_version
        cliproxy_repo = self.args.cliproxy_repo
        require_sha256 = bool(getattr(self.args, "require_sha256", False))

        output.progress(
            f"bootstrap:download cliproxy_repo={cliproxy_repo} cliproxy_version={cliproxy_version}"
        )
        cliproxy = download_cliproxyapi_plus(
            runtime_bin_dir,
            version=cliproxy_version,
            repo=cliproxy_repo,
            require_sha256=require_sha256,
        )
        if not validate_cliproxy_binary(cliproxy):
            raise RuntimeError(f"Invalid CLIProxyAPIPlus binary downloaded: {cliproxy}")

        write_installed_version(self.config["paths"]["runtime_dir"], cliproxy_version)
        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "cliproxyapi_plus": str(cliproxy),
                        "cliproxy_version": str(cliproxy_version),
                        "cliproxy_repo": str(cliproxy_repo),
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        print(f"cliproxyapi_plus={cliproxy}", file=stdout)
        return 0


def _check_latest_version(current_version: str, repo: str) -> dict[str, str] | None:
    """Backward-compatible wrapper for latest-version checks."""
    return check_latest_version(current_version=current_version, repo=repo)


def _confirm_update(stdout: TextIO, stderr: TextIO) -> bool:
    """Prompt the user to confirm the update. Returns True if confirmed."""
    print("Proceed with update? [y/N] ", end="", file=stdout, flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


class BootstrapUpdateCommand(BaseCommand):
    """Check for and apply CLIProxyAPIPlus updates."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute bootstrap update command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        runtime_dir = self.config["paths"]["runtime_dir"]
        repo = self.args.cliproxy_repo
        auto_yes = self.args.yes
        require_sha256 = bool(getattr(self.args, "require_sha256", False))

        current_version = read_installed_version(runtime_dir, DEFAULT_CLIPROXY_VERSION)

        update_info = _check_latest_version(current_version, repo)

        if update_info is None:
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": True,
                        "command": command_id_from_args(self.args),
                        "data": {
                            "updated": False,
                            "current_version": current_version,
                            "latest_version": current_version,
                            "repo": repo,
                        },
                        "warnings": [],
                        "errors": [],
                    }
                )
                return 0
            print(
                f"cliproxyapi_plus:up_to_date current={current_version}",
                file=stdout,
            )
            return 0

        latest_version = update_info["latest_version"]
        print(
            f"cliproxyapi_plus:update_available "
            f"current={current_version} latest={latest_version}",
            file=stdout,
        )

        if not auto_yes:
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(self.args),
                        "data": {
                            "updated": False,
                            "current_version": current_version,
                            "latest_version": latest_version,
                            "repo": repo,
                        },
                        "warnings": [],
                        "errors": [
                            {
                                "type": "ConfigError",
                                "message": "bootstrap update requires --yes in non-legacy output formats",
                            }
                        ],
                    }
                )
                return 2
            if not output.interactive:
                print(
                    "bootstrap update requires --yes in non-interactive mode",
                    file=stderr,
                )
                return 2
            if not _confirm_update(stdout, stderr):
                print("cliproxyapi_plus:update_cancelled", file=stdout)
                return 0

        output.progress(
            f"bootstrap:update downloading version={latest_version} repo={repo}"
        )
        updated = perform_update(
            config=self.config,
            latest_version=latest_version,
            repo=repo,
            require_sha256=require_sha256,
        )
        cliproxy = updated["cliproxyapi_plus"]
        restarted_pid = updated["restarted_pid"]

        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "updated": True,
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "repo": repo,
                        "cliproxyapi_plus": str(cliproxy),
                        "restarted_pid": restarted_pid,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        print(
            f"cliproxyapi_plus:updated version={latest_version}",
            file=stdout,
        )
        if restarted_pid is not None:
            print(
                f"{CLIPROXYAPI_PLUS_SERVICE}:restarted pid={restarted_pid}",
                file=stdout,
            )

        return 0
