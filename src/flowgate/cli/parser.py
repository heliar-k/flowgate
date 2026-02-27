"""
Argument parser for FlowGate CLI.

This module contains the argparse configuration and
command-line argument parsing logic.
"""

from __future__ import annotations

import argparse

from ..bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for FlowGate CLI."""
    parser = argparse.ArgumentParser(prog="flowgate")
    parser.add_argument("--config", default="config/flowgate.yaml")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Show stack traces on errors and enable debug logging",
    )
    parser.add_argument(
        "--format",
        default="legacy",
        choices=["auto", "legacy", "kv", "json"],
        help="Output format (default: legacy). Use json/kv for scripts.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Reduce non-essential output (progress messages, hints)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        default=False,
        help="Avoid unicode status icons in legacy output",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    health_parser = sub.add_parser("health")
    health_parser.add_argument("--verbose", action="store_true", help="Show detailed health information")
    sub.add_parser("doctor")

    integration = sub.add_parser("integration")
    integration_sub = integration.add_subparsers(dest="integration_cmd", required=True)
    integration_print = integration_sub.add_parser("print")
    integration_print.add_argument("client", choices=["codex", "claude-code"])
    integration_apply = integration_sub.add_parser("apply")
    integration_apply.add_argument("client", choices=["codex", "claude-code"])
    integration_apply.add_argument("--target", default="")
    integration_apply.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show planned changes without modifying files",
    )
    integration_apply.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Skip confirmation prompts for non-interactive runs",
    )

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="provider", required=True)
    auth_sub.add_parser("list")
    auth_sub.add_parser("status")

    login_any = auth_sub.add_parser("login")
    login_any.add_argument("login_provider")
    login_any.add_argument("--timeout", type=float, default=120)
    login_any.add_argument("--poll-interval", type=float, default=2)

    import_headless_any = auth_sub.add_parser("import-headless")
    import_headless_any.add_argument("import_provider")
    import_headless_any.add_argument("--source", default="~/.codex/auth.json")
    import_headless_any.add_argument("--dest-dir", default="")

    service = sub.add_parser("service")
    service_sub = service.add_subparsers(dest="service_cmd", required=True)
    for action in ("start", "stop", "restart"):
        action_parser = service_sub.add_parser(action)
        action_parser.add_argument("target", nargs="?", default="all")

    bootstrap = sub.add_parser("bootstrap")
    bootstrap_sub = bootstrap.add_subparsers(dest="bootstrap_cmd", required=True)
    download = bootstrap_sub.add_parser("download")
    download.add_argument("--cliproxy-version", default=DEFAULT_CLIPROXY_VERSION)
    download.add_argument("--cliproxy-repo", default=DEFAULT_CLIPROXY_REPO)
    download.add_argument(
        "--require-sha256",
        action="store_true",
        default=False,
        help="Require a sha256 checksum asset to be present for CLIProxyAPIPlus downloads",
    )

    update = bootstrap_sub.add_parser("update")
    update.add_argument("--cliproxy-repo", default=DEFAULT_CLIPROXY_REPO)
    update.add_argument("--yes", "-y", action="store_true", default=False)
    update.add_argument(
        "--require-sha256",
        action="store_true",
        default=False,
        help="Require a sha256 checksum asset to be present for CLIProxyAPIPlus downloads",
    )

    return parser
