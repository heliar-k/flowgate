"""
Auth command handlers for FlowGate CLI.

This module contains command handlers for authentication operations including
OAuth login, headless import, and provider status checks.
"""
from __future__ import annotations

import sys
from typing import Any, TextIO

from ...config import ConfigError
from ...process import ProcessSupervisor
from ...security import check_secret_file_permissions
from ..error_handler import handle_command_errors
from ..utils import _default_auth_dir
from .base import BaseCommand


def _auth_providers(config: dict[str, Any]) -> dict[str, Any]:
    """Extract auth providers from config."""
    auth = config.get("auth", {})
    if isinstance(auth, dict):
        providers_raw = auth.get("providers", {})
        if isinstance(providers_raw, dict):
            return providers_raw

    return {}


def _effective_secret_files(config: dict[str, Any]) -> list[str]:
    """Collect all secret files from config and auth directory."""
    from pathlib import Path

    paths: set[str] = set()
    for value in config.get("secret_files", []):
        if isinstance(value, str) and value.strip():
            paths.add(str(Path(value).resolve()))

    default_auth_dir = Path(_default_auth_dir(config))
    if default_auth_dir.exists():
        for item in default_auth_dir.glob("*.json"):
            paths.add(str(item.resolve()))

    return sorted(paths)


class AuthListCommand(BaseCommand):
    """List available authentication providers and their capabilities."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute auth list command."""
        # Import here to avoid circular dependency
        from ...auth_methods import headless_import_handlers

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout

        providers_map = _auth_providers(self.config)
        providers = sorted(str(name) for name in providers_map.keys())
        handlers = headless_import_handlers()

        if not providers:
            print("oauth_providers=none", file=stdout)
            print("headless_import_providers=none", file=stdout)
            return 0

        for provider in providers:
            provider_cfg = providers_map.get(provider, {})
            oauth_supported = bool(
                isinstance(provider_cfg, dict)
                and provider_cfg.get("auth_url_endpoint")
                and provider_cfg.get("status_endpoint")
            )
            headless = "yes" if provider in handlers else "no"
            print(
                f"provider={provider} oauth_login={'yes' if oauth_supported else 'no'} headless_import={headless}",
                file=stdout,
            )

        supported = sorted(provider for provider in providers if provider in handlers)
        print(f"oauth_providers={','.join(providers)}", file=stdout)
        print(
            f"headless_import_providers={','.join(supported) if supported else 'none'}",
            file=stdout,
        )
        return 0


class AuthStatusCommand(BaseCommand):
    """Display authentication status and provider configuration."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute auth status command."""
        # Import here to avoid circular dependency
        from ...auth_methods import headless_import_handlers

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout

        providers_map = _auth_providers(self.config)
        providers = sorted(str(name) for name in providers_map.keys())
        handlers = headless_import_handlers()

        print(f"default_auth_dir={_default_auth_dir(self.config)}", file=stdout)
        issues = check_secret_file_permissions(_effective_secret_files(self.config))
        print(f"secret_permission_issues={len(issues)}", file=stdout)

        if not providers:
            print("providers=none", file=stdout)
            return 0

        for provider in providers:
            provider_cfg = providers_map.get(provider, {})
            method = "unknown"
            oauth_supported = False
            if isinstance(provider_cfg, dict):
                method = str(provider_cfg.get("method", "oauth_poll"))
                oauth_supported = bool(
                    provider_cfg.get("auth_url_endpoint")
                    and provider_cfg.get("status_endpoint")
                )
            print(
                (
                    f"provider={provider} "
                    f"method={method} "
                    f"oauth_login={'yes' if oauth_supported else 'no'} "
                    f"headless_import={'yes' if provider in handlers else 'no'}"
                ),
                file=stdout,
            )

        return 0


class AuthLoginCommand(BaseCommand):
    """Perform OAuth login for a provider."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute auth login command."""
        # Import here to avoid circular dependency
        from ...oauth import fetch_auth_url, poll_auth_status

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        provider = self.args.login_provider
        timeout = self.args.timeout
        poll_interval = self.args.poll_interval

        supervisor = ProcessSupervisor(self.config["paths"]["runtime_dir"])
        providers = _auth_providers(self.config)
        if provider not in providers:
            supervisor.record_event(
                "oauth_login",
                provider=provider,
                result="failed",
                detail="provider-not-configured",
            )
            available = ",".join(sorted(str(k) for k in providers.keys())) or "none"
            print(
                f"OAuth provider not configured: {provider}; available={available}",
                file=stderr,
            )
            return 2

        provider_cfg = providers[provider]
        auth_url_endpoint = provider_cfg.get("auth_url_endpoint")
        status_endpoint = provider_cfg.get("status_endpoint")
        if not auth_url_endpoint or not status_endpoint:
            supervisor.record_event(
                "oauth_login", provider=provider, result="failed", detail="endpoint-missing"
            )
            print(f"OAuth endpoints not complete for provider={provider}", file=stderr)
            return 2

        try:
            url = fetch_auth_url(auth_url_endpoint, timeout=5)
            print(f"login_url={url}", file=stdout)
            status = poll_auth_status(
                status_endpoint,
                timeout_seconds=timeout,
                poll_interval_seconds=poll_interval,
            )
            supervisor.record_event("oauth_login", provider=provider, result="success")
            print(f"oauth_status={status}", file=stdout)
            return 0
        except (TimeoutError, RuntimeError, ValueError, OSError) as exc:
            supervisor.record_event(
                "oauth_login", provider=provider, result="failed", detail=str(exc)
            )
            raise ConfigError(
                f"OAuth login failed: {exc} "
                "hint=verify auth endpoints, run `auth status`, then retry with a larger --timeout if needed"
            ) from exc


class AuthImportCommand(BaseCommand):
    """Import authentication credentials from headless source."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute auth import-headless command."""
        # Import here to avoid circular dependency
        from ...auth_methods import get_headless_import_handler, headless_import_handlers

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        provider = self.args.import_provider
        source = self.args.source
        dest_dir = self.args.dest_dir if self.args.dest_dir else None

        handler = get_headless_import_handler(provider)
        if handler is None:
            supported = ",".join(sorted(headless_import_handlers().keys())) or "none"
            print(
                f"headless import not supported for provider={provider}; supported={supported}",
                file=stderr,
            )
            return 2

        resolved_dest = dest_dir
        if not resolved_dest:
            resolved_dest = _default_auth_dir(self.config)

        try:
            saved = handler(source, resolved_dest)
        except (FileNotFoundError, ValueError, OSError, RuntimeError) as exc:
            raise ConfigError(f"headless import failed: {exc}") from exc

        supervisor = ProcessSupervisor(self.config["paths"]["runtime_dir"])
        supervisor.record_event(
            "auth_import",
            provider=provider,
            result="success",
            detail=f"method=headless path={saved}",
        )
        print(f"saved_auth={saved}", file=stdout)
        return 0
