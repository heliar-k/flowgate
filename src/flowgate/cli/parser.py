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

    sub = parser.add_subparsers(dest="command", required=True)

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_cmd", required=True)
    profile_sub.add_parser("list")
    p_set = profile_sub.add_parser("set")
    p_set.add_argument("name")

    sub.add_parser("status")
    sub.add_parser("health")
    sub.add_parser("doctor")

    integration = sub.add_parser("integration")
    integration_sub = integration.add_subparsers(dest="integration_cmd", required=True)
    integration_print = integration_sub.add_parser("print")
    integration_print.add_argument("client", choices=["codex", "claude-code"])
    integration_apply = integration_sub.add_parser("apply")
    integration_apply.add_argument("client", choices=["codex", "claude-code"])
    integration_apply.add_argument("--target", default="")

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

    for provider in ("codex", "copilot"):
        provider_parser = auth_sub.add_parser(provider)
        provider_sub = provider_parser.add_subparsers(dest="auth_cmd", required=True)
        login = provider_sub.add_parser("login")
        login.add_argument("--timeout", type=float, default=120)
        login.add_argument("--poll-interval", type=float, default=2)
        if provider == "codex":
            import_headless = provider_sub.add_parser("import-headless")
            import_headless.add_argument("--source", default="~/.codex/auth.json")
            import_headless.add_argument("--dest-dir", default="")

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

    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="config_cmd", required=True)
    migrate = config_sub.add_parser("migrate")
    migrate.add_argument("--to-version", type=int, default=2, dest="to_version")
    migrate.add_argument("--dry-run", action="store_true", dest="dry_run")

    return parser
