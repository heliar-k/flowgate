"""
Auth command handlers for FlowGate CLI.

This module contains command handlers for authentication operations including
OAuth login, headless import, and provider status checks.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO

from flowgate.core.config import ConfigError
from flowgate.core.process import ProcessError, ProcessSupervisor
from flowgate.core.security import check_secret_file_permissions
from flowgate.cli.base import BaseCommand
from flowgate.cli.error_handler import handle_command_errors
from flowgate.cli.helpers import _default_auth_dir, effective_secret_files
from flowgate.cli.output import Output, command_id_from_args


def _auth_providers(config: dict[str, Any]) -> dict[str, Any]:
    """Extract auth providers from config."""
    auth = config.get("auth", {})
    if isinstance(auth, dict):
        providers_raw = auth.get("providers", {})
        if isinstance(providers_raw, dict):
            return providers_raw

    return {}


def _derive_auth_endpoints(
    config: dict[str, Any], provider: str
) -> tuple[str | None, str | None]:
    """Derive auth endpoints from cliproxyapi_plus service config.

    Returns:
        (auth_url_endpoint, status_endpoint) or (None, None) if cannot derive
    """
    services = config.get("services", {})
    cliproxy = services.get("cliproxyapi_plus", {})

    host = cliproxy.get("host")
    port = cliproxy.get("port")

    if not host or not port:
        return None, None

    # Map provider name to URL path
    provider_path_map = {
        "codex": "codex",
        "copilot": "github-copilot",
    }

    provider_path = provider_path_map.get(provider)
    if not provider_path:
        return None, None

    base_url = f"http://{host}:{port}"
    auth_url = f"{base_url}/v0/management/oauth/{provider_path}/auth-url"
    status_url = f"{base_url}/v0/management/oauth/{provider_path}/status"

    return auth_url, status_url


class AuthListCommand(BaseCommand):
    """List available authentication providers and their capabilities."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute auth list command."""
        # Import here to avoid circular dependency
        from flowgate.core.auth import headless_import_handlers

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        providers_map = _auth_providers(self.config)
        providers = sorted(str(name) for name in providers_map.keys())
        handlers = headless_import_handlers()

        if not providers:
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": True,
                        "command": command_id_from_args(self.args),
                        "data": {
                            "providers": [],
                            "oauth_providers": [],
                            "headless_import_providers": [],
                        },
                        "warnings": [],
                        "errors": [],
                    }
                )
                return 0

            print("oauth_providers=none", file=stdout)
            print("headless_import_providers=none", file=stdout)
            return 0

        provider_rows: list[dict[str, Any]] = []
        for provider in providers:
            provider_cfg = providers_map.get(provider, {})
            oauth_supported = bool(
                isinstance(provider_cfg, dict)
                and provider_cfg.get("auth_url_endpoint")
                and provider_cfg.get("status_endpoint")
            )
            headless = "yes" if provider in handlers else "no"
            provider_rows.append(
                {
                    "provider": provider,
                    "oauth_login": bool(oauth_supported),
                    "headless_import": provider in handlers,
                }
            )
            if output.format == "legacy":
                print(
                    f"provider={provider} oauth_login={'yes' if oauth_supported else 'no'} headless_import={headless}",
                    file=stdout,
                )

        supported = sorted(provider for provider in providers if provider in handlers)
        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "providers": provider_rows,
                        "oauth_providers": providers,
                        "headless_import_providers": supported,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

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
        from flowgate.core.auth import headless_import_handlers

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        providers_map = _auth_providers(self.config)
        providers = sorted(str(name) for name in providers_map.keys())
        handlers = headless_import_handlers()

        issues = check_secret_file_permissions(effective_secret_files(self.config))
        default_dir = _default_auth_dir(self.config)
        secret_issue_count = len(issues)

        if output.format != "legacy":
            provider_rows: list[dict[str, Any]] = []
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
                provider_rows.append(
                    {
                        "provider": provider,
                        "method": method,
                        "oauth_login": bool(oauth_supported),
                        "headless_import": provider in handlers,
                    }
                )

            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "default_auth_dir": default_dir,
                        "secret_permission_issues": secret_issue_count,
                        "providers": provider_rows,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        print(f"default_auth_dir={default_dir}", file=stdout)
        print(f"secret_permission_issues={secret_issue_count}", file=stdout)

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
        from flowgate.core.auth import fetch_auth_url, poll_auth_status

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        provider = self.args.login_provider
        timeout = self.args.timeout
        poll_interval = self.args.poll_interval

        supervisor = ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        providers = _auth_providers(self.config)
        if provider not in providers:
            supervisor.record_event(
                "oauth_login",
                provider=provider,
                result="failed",
                detail="provider-not-configured",
            )
            available = ",".join(sorted(str(k) for k in providers.keys())) or "none"
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(self.args),
                        "data": {
                            "provider": provider,
                            "available": available.split(",")
                            if available != "none"
                            else [],
                        },
                        "warnings": [],
                        "errors": [
                            {
                                "type": "ConfigError",
                                "message": f"OAuth provider not configured: {provider}",
                            }
                        ],
                    }
                )
            print(
                f"OAuth provider not configured: {provider}; available={available}",
                file=stderr,
            )
            return 2

        provider_cfg = providers[provider]
        auth_url_endpoint = provider_cfg.get("auth_url_endpoint")
        status_endpoint = provider_cfg.get("status_endpoint")

        # If endpoints are missing, try to derive from cliproxyapi_plus service config
        if not auth_url_endpoint or not status_endpoint:
            derived_auth, derived_status = _derive_auth_endpoints(self.config, provider)
            if not auth_url_endpoint:
                auth_url_endpoint = derived_auth
            if not status_endpoint:
                status_endpoint = derived_status

        if not auth_url_endpoint or not status_endpoint:
            supervisor.record_event(
                "oauth_login",
                provider=provider,
                result="failed",
                detail="endpoint-missing",
            )
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(self.args),
                        "data": {"provider": provider},
                        "warnings": [],
                        "errors": [
                            {
                                "type": "ConfigError",
                                "message": f"OAuth endpoints not configured or derivable for provider={provider}",
                            }
                        ],
                    }
                )
            print(
                f"OAuth endpoints not configured or derivable for provider={provider}",
                file=stderr,
            )
            return 2

        try:
            output.progress(
                f"auth:login provider={provider} polling every={poll_interval}s timeout={timeout}s"
            )
            url = fetch_auth_url(auth_url_endpoint, timeout=5)
            status = poll_auth_status(
                status_endpoint,
                timeout_seconds=timeout,
                poll_interval_seconds=poll_interval,
            )
            supervisor.record_event("oauth_login", provider=provider, result="success")
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": True,
                        "command": command_id_from_args(self.args),
                        "data": {
                            "provider": provider,
                            "login_url": url,
                            "oauth_status": status,
                        },
                        "warnings": [],
                        "errors": [],
                    }
                )
                return 0

            print(f"login_url={url}", file=stdout)
            print(f"oauth_status={status}", file=stdout)
            return 0
        except (TimeoutError, RuntimeError, ValueError, OSError) as exc:
            supervisor.record_event(
                "oauth_login", provider=provider, result="failed", detail=str(exc)
            )
            raise ProcessError(
                f"OAuth login failed: {exc} "
                "hint=verify auth endpoints, run `auth status`, then retry with a larger --timeout if needed"
            ) from exc


class AuthImportCommand(BaseCommand):
    """Import authentication credentials from headless source."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute auth import-headless command."""
        # Import here to avoid circular dependency
        from flowgate.core.auth import (
            get_headless_import_handler,
            headless_import_handlers,
        )

        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr
        output: Output = getattr(self.args, "_output", None) or Output.from_args(
            self.args, stdout=stdout, stderr=stderr
        )

        provider = self.args.import_provider
        source = self.args.source
        dest_dir = self.args.dest_dir if self.args.dest_dir else None

        handler = get_headless_import_handler(provider)
        if handler is None:
            supported = ",".join(sorted(headless_import_handlers().keys())) or "none"
            if output.format != "legacy":
                output.emit_envelope(
                    {
                        "ok": False,
                        "command": command_id_from_args(self.args),
                        "data": {
                            "provider": provider,
                            "supported": supported.split(",")
                            if supported != "none"
                            else [],
                        },
                        "warnings": [],
                        "errors": [
                            {
                                "type": "ConfigError",
                                "message": f"headless import not supported for provider={provider}",
                            }
                        ],
                    }
                )
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
            raise ProcessError(f"headless import failed: {exc}") from exc

        supervisor = ProcessSupervisor(
            self.config["paths"]["runtime_dir"],
            events_log=self.config["paths"]["log_file"],
        )
        supervisor.record_event(
            "auth_import",
            provider=provider,
            result="success",
            detail=f"method=headless path={saved}",
        )
        if output.format != "legacy":
            output.emit_envelope(
                {
                    "ok": True,
                    "command": command_id_from_args(self.args),
                    "data": {
                        "provider": provider,
                        "saved_auth": saved,
                        "dest_dir": resolved_dest,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            return 0

        print(f"saved_auth={saved}", file=stdout)
        return 0
