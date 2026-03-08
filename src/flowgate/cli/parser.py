"""
Argument parser for FlowGate CLI.

This module contains the argparse configuration and
command-line argument parsing logic.
"""

from __future__ import annotations

import argparse

from flowgate.core.bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for FlowGate CLI."""
    parser = argparse.ArgumentParser(
        prog="flowgate",
        description="FlowGate - local control tool for managing CLIProxyAPIPlus",
        epilog="""examples:
  flowgate --config config/flowgate.yaml status
  flowgate --config config/flowgate.yaml service start all
  flowgate --config config/flowgate.yaml auth login codex --timeout 180
  flowgate --config config/flowgate.yaml bootstrap download
  flowgate --config config/flowgate.yaml doctor""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default="config/flowgate.yaml",
        help="Path to FlowGate config file (default: config/flowgate.yaml)",
    )
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

    sub = parser.add_subparsers(dest="command", required=True, title="commands")

    sub.add_parser("status", help="Show current system status (services, auth)")
    health_parser = sub.add_parser("health", help="Check service health")
    health_parser.add_argument(
        "--verbose", action="store_true", help="Show detailed health information"
    )
    sub.add_parser(
        "doctor",
        help="Run diagnostics (config validation, dependency checks, permissions)",
    )

    auth = sub.add_parser("auth", help="Authentication management")
    auth_sub = auth.add_subparsers(
        dest="provider", required=True, title="auth commands"
    )
    auth_sub.add_parser(
        "list", help="List available OAuth providers and their capabilities"
    )
    auth_sub.add_parser("status", help="Show current authentication status")

    login_any = auth_sub.add_parser(
        "login", help="Perform OAuth login flow (e.g. codex, github-copilot)"
    )
    login_any.add_argument(
        "login_provider", metavar="provider", help="OAuth provider name"
    )
    login_any.add_argument(
        "--timeout",
        type=float,
        default=120,
        help="OAuth polling timeout in seconds (default: 120)",
    )
    login_any.add_argument(
        "--poll-interval",
        type=float,
        default=2,
        help="Polling interval in seconds (default: 2)",
    )

    import_headless_any = auth_sub.add_parser(
        "import-headless",
        help="Import auth credentials from file (for non-interactive environments)",
    )
    import_headless_any.add_argument(
        "import_provider", metavar="provider", help="OAuth provider name"
    )
    import_headless_any.add_argument(
        "--source",
        default="~/.codex/auth.json",
        help="Source auth file path (default: ~/.codex/auth.json)",
    )
    import_headless_any.add_argument(
        "--dest-dir", default="", help="Destination directory for imported credentials"
    )

    service = sub.add_parser("service", help="Service lifecycle management")
    service_sub = service.add_subparsers(
        dest="service_cmd", required=True, title="service commands"
    )
    service_help = {
        "start": "Start services",
        "stop": "Stop services",
        "restart": "Restart services",
    }
    for action in ("start", "stop", "restart"):
        action_parser = service_sub.add_parser(action, help=service_help[action])
        action_parser.add_argument(
            "target",
            nargs="?",
            default="all",
            help='Service name or "all" (default: all)',
        )

    bootstrap = sub.add_parser("bootstrap", help="Runtime environment initialization")
    bootstrap_sub = bootstrap.add_subparsers(
        dest="bootstrap_cmd", required=True, title="bootstrap commands"
    )
    download = bootstrap_sub.add_parser(
        "download", help="Download runtime binary (CLIProxyAPIPlus)"
    )
    download.add_argument(
        "--cliproxy-version",
        default=DEFAULT_CLIPROXY_VERSION,
        help=f"CLIProxyAPIPlus version (default: {DEFAULT_CLIPROXY_VERSION})",
    )
    download.add_argument(
        "--cliproxy-repo",
        default=DEFAULT_CLIPROXY_REPO,
        help=f"GitHub repository (default: {DEFAULT_CLIPROXY_REPO})",
    )
    download.add_argument(
        "--require-sha256",
        action="store_true",
        default=False,
        help="Require a sha256 checksum asset to be present for CLIProxyAPIPlus downloads",
    )

    update = bootstrap_sub.add_parser(
        "update", help="Check for and apply CLIProxyAPIPlus updates"
    )
    update.add_argument(
        "--cliproxy-repo",
        default=DEFAULT_CLIPROXY_REPO,
        help=f"GitHub repository (default: {DEFAULT_CLIPROXY_REPO})",
    )
    update.add_argument(
        "--yes",
        "-y",
        action="store_true",
        default=False,
        help="Skip confirmation prompt",
    )
    update.add_argument(
        "--require-sha256",
        action="store_true",
        default=False,
        help="Require a sha256 checksum asset to be present for CLIProxyAPIPlus downloads",
    )

    return parser
