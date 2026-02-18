"""
Bootstrap command handlers for FlowGate CLI.

This module contains command handlers for downloading and setting up
runtime dependencies (CLIProxyAPIPlus binary and LiteLLM runner).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

from ...bootstrap import (
    download_cliproxyapi_plus,
    prepare_litellm_runner,
    validate_cliproxy_binary,
    validate_litellm_runner,
)
from ...cliproxyapiplus_update_check import (
    write_cliproxyapiplus_installed_version,
)
from .base import BaseCommand


class BootstrapDownloadCommand(BaseCommand):
    """Download and prepare runtime binaries (CLIProxyAPIPlus and LiteLLM)."""

    def execute(self) -> int:
        """Execute bootstrap download command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        runtime_bin_dir = Path(self.config["paths"]["runtime_dir"]) / "bin"
        cliproxy_version = self.args.cliproxy_version
        cliproxy_repo = self.args.cliproxy_repo

        try:
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
        except Exception as exc:  # noqa: BLE001
            print(f"bootstrap failed: {exc}", file=stderr)
            return 1

        write_cliproxyapiplus_installed_version(
            self.config["paths"]["runtime_dir"], cliproxy_version
        )
        print(f"cliproxyapi_plus={cliproxy}", file=stdout)
        print(f"litellm={litellm}", file=stdout)
        return 0
