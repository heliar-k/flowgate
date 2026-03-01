#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from flowgate.bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION
from flowgate.cliproxyapiplus_auto_update import check_latest_version, perform_update
from flowgate.cliproxyapiplus_update_check import read_cliproxyapiplus_installed_version
from flowgate.config import load_router_config
from flowgate.constants import CLIPROXYAPI_PLUS_SERVICE


def _confirm_update(stdout: TextIO) -> bool:
    print("Proceed with update? [y/N] ", end="", file=stdout, flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check and update CLIProxyAPIPlus binary, then restart if running."
    )
    parser.add_argument("--config", required=True, help="Path to flowgate config file")
    parser.add_argument("--cliproxy-repo", default=DEFAULT_CLIPROXY_REPO)
    parser.add_argument("--yes", "-y", action="store_true", default=False)
    parser.add_argument(
        "--require-sha256",
        action="store_true",
        default=False,
        help="Require sha256 checksum asset for downloads",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    stdout: TextIO = sys.stdout
    stderr: TextIO = sys.stderr

    config_path = Path(args.config)
    config = load_router_config(config_path)
    runtime_dir = config["paths"]["runtime_dir"]
    current_version = read_cliproxyapiplus_installed_version(
        runtime_dir, DEFAULT_CLIPROXY_VERSION
    )

    update_info = check_latest_version(
        current_version=current_version,
        repo=args.cliproxy_repo,
    )
    if update_info is None:
        print(f"cliproxyapi_plus:up_to_date current={current_version}", file=stdout)
        return 0

    latest_version = update_info["latest_version"]
    print(
        f"cliproxyapi_plus:update_available current={current_version} latest={latest_version}",
        file=stdout,
    )

    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "bootstrap update requires --yes in non-interactive mode", file=stderr
            )
            return 2
        if not _confirm_update(stdout):
            print("cliproxyapi_plus:update_cancelled", file=stdout)
            return 0

    updated = perform_update(
        config=config,
        latest_version=latest_version,
        repo=args.cliproxy_repo,
        require_sha256=bool(args.require_sha256),
    )
    print(f"cliproxyapi_plus:updated version={latest_version}", file=stdout)

    restarted_pid = updated["restarted_pid"]
    if restarted_pid is not None:
        print(f"{CLIPROXYAPI_PLUS_SERVICE}:restarted pid={restarted_pid}", file=stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
