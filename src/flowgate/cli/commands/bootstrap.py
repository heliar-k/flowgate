"""
Bootstrap command handlers for FlowGate CLI.

This module contains command handlers for downloading and setting up
runtime dependencies (CLIProxyAPIPlus binary and LiteLLM runner).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, TextIO

from ...bootstrap import (
    DEFAULT_CLIPROXY_REPO,
    DEFAULT_CLIPROXY_VERSION,
    _http_get_json,
    download_cliproxyapi_plus,
    prepare_litellm_runner,
    validate_cliproxy_binary,
    validate_litellm_runner,
)
from ...cliproxyapiplus_update_check import (
    _is_newer_version,
    read_cliproxyapiplus_installed_version,
    write_cliproxyapiplus_installed_version,
)
from ...constants import CLIPROXYAPI_PLUS_SERVICE
from ...process import ProcessSupervisor
from ..error_handler import handle_command_errors
from .base import BaseCommand


class BootstrapDownloadCommand(BaseCommand):
    """Download and prepare runtime binaries (CLIProxyAPIPlus and LiteLLM)."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute bootstrap download command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout

        runtime_bin_dir = Path(self.config["paths"]["runtime_dir"]) / "bin"
        cliproxy_version = self.args.cliproxy_version
        cliproxy_repo = self.args.cliproxy_repo

        cliproxy = download_cliproxyapi_plus(
            runtime_bin_dir,
            version=cliproxy_version,
            repo=cliproxy_repo,
        )
        litellm = prepare_litellm_runner(runtime_bin_dir)
        if not validate_cliproxy_binary(cliproxy):
            raise RuntimeError(f"Invalid CLIProxyAPIPlus binary downloaded: {cliproxy}")
        if not validate_litellm_runner(litellm):
            raise RuntimeError(f"Invalid litellm runner generated: {litellm}")

        write_cliproxyapiplus_installed_version(
            self.config["paths"]["runtime_dir"], cliproxy_version
        )
        print(f"cliproxyapi_plus={cliproxy}", file=stdout)
        print(f"litellm={litellm}", file=stdout)
        return 0


def _check_latest_version(
    current_version: str, repo: str
) -> dict[str, str] | None:
    """Check for the latest CLIProxyAPIPlus version via GitHub API (no cache).

    Returns a dict with current_version, latest_version and release_url
    if an update is available, or None if already up to date.
    """
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    data = _http_get_json(api_url)
    latest = str(data.get("tag_name", "")).strip()
    release_url = str(data.get("html_url", "")).strip()
    if not latest:
        return None
    if _is_newer_version(latest, current_version):
        return {
            "current_version": current_version,
            "latest_version": latest,
            "release_url": release_url,
        }
    return None


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

        runtime_dir = self.config["paths"]["runtime_dir"]
        runtime_bin_dir = Path(runtime_dir) / "bin"
        repo = self.args.cliproxy_repo
        auto_yes = self.args.yes

        current_version = read_cliproxyapiplus_installed_version(
            runtime_dir, DEFAULT_CLIPROXY_VERSION
        )

        update_info = _check_latest_version(current_version, repo)

        if update_info is None:
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

        if not auto_yes and not _confirm_update(stdout, stderr):
            print("cliproxyapi_plus:update_cancelled", file=stdout)
            return 0

        cliproxy = download_cliproxyapi_plus(
            runtime_bin_dir, version=latest_version, repo=repo
        )
        if not validate_cliproxy_binary(cliproxy):
            raise RuntimeError(
                f"Invalid CLIProxyAPIPlus binary downloaded: {cliproxy}"
            )

        write_cliproxyapiplus_installed_version(runtime_dir, latest_version)
        print(
            f"cliproxyapi_plus:updated version={latest_version}",
            file=stdout,
        )

        # Auto-restart cliproxyapi_plus if it is running
        supervisor = ProcessSupervisor(runtime_dir)
        if supervisor.is_running(CLIPROXYAPI_PLUS_SERVICE):
            service_cfg = self.config["services"].get(CLIPROXYAPI_PLUS_SERVICE, {})
            args = service_cfg.get("command", {}).get("args", [])
            cwd = service_cfg.get("command", {}).get("cwd") or os.getcwd()
            pid = supervisor.restart(CLIPROXYAPI_PLUS_SERVICE, args, cwd=cwd)
            print(
                f"{CLIPROXYAPI_PLUS_SERVICE}:restarted pid={pid}",
                file=stdout,
            )

        return 0
