"""Test configuration data factory (config_version 3).

This module provides factory methods to create v3 (cliproxy-only) FlowGate
configs and matching CLIProxyAPIPlus configs for unit tests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from flowgate.core.constants import (
    DEFAULT_READINESS_PATH,
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORTS,
)


class ConfigFactory:
    """Factory for creating v3 test configuration data."""

    @staticmethod
    def minimal(
        *,
        runtime_dir: str = ".router/runtime",
        log_file: str | None = None,
        cliproxy_config_file: str = "cliproxyapi.yaml",
    ) -> dict[str, Any]:
        """Create a minimal valid v3 FlowGate configuration dict."""
        if log_file is None:
            log_file = f"{runtime_dir}/events.log"

        return {
            "config_version": 3,
            "paths": {"runtime_dir": runtime_dir, "log_file": log_file},
            "cliproxyapi_plus": {"config_file": cliproxy_config_file},
            "auth": {"providers": {}},
            "secret_files": [],
        }

    @staticmethod
    def paths(
        *,
        runtime_dir: str = ".router/runtime",
        log_file: str | None = None,
    ) -> dict[str, str]:
        """Create v3 paths section."""
        if log_file is None:
            log_file = f"{runtime_dir}/events.log"
        return {"runtime_dir": runtime_dir, "log_file": log_file}

    @staticmethod
    def cliproxyapi_config(
        *,
        host: str = DEFAULT_SERVICE_HOST,
        port: int = DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
    ) -> dict[str, Any]:
        """Create a minimal CLIProxyAPIPlus config dict (host/port only)."""
        return {"host": host, "port": port}

    @staticmethod
    def write_minimal_v3(tmp_path: Path) -> Path:
        """Write `flowgate.yaml` + `cliproxyapi.yaml` under a temp project root.

        The layout matches what FlowGate expects:
        - <root>/config/flowgate.yaml
        - <root>/config/cliproxyapi.yaml
        - <root>/runtime/ (paths.runtime_dir)
        """
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)

        cliproxy_path = cfg_dir / "cliproxyapi.yaml"
        cliproxy_path.write_text(
            json.dumps(ConfigFactory.cliproxyapi_config()),
            encoding="utf-8",
        )

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        flowgate_path = cfg_dir / "flowgate.yaml"
        flowgate = ConfigFactory.minimal(
            runtime_dir=str(runtime_dir),
            log_file=str(runtime_dir / "events.log"),
            cliproxy_config_file="cliproxyapi.yaml",
        )
        flowgate_path.write_text(json.dumps(flowgate), encoding="utf-8")
        return flowgate_path

    @staticmethod
    def auth_provider(
        provider_name: str,
        *,
        host: str = DEFAULT_SERVICE_HOST,
        port: int = DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
        method: str = "oauth_poll",
    ) -> dict[str, Any]:
        """Create an auth.providers.<name> entry.

        Uses the same URLs as `_derive_auth_endpoints()` in the auth CLI command.
        """
        provider_path_map = {
            "codex": "codex",
            "copilot": "github-copilot",
        }
        provider_path = provider_path_map.get(provider_name, provider_name)
        base_url = f"http://{host}:{port}"
        return {
            "method": method,
            "auth_url_endpoint": f"{base_url}/v0/management/oauth/{provider_path}/auth-url",
            "status_endpoint": f"{base_url}/v0/management/oauth/{provider_path}/status",
        }

    @staticmethod
    def with_auth(
        providers: list[str] | None = None,
        *,
        host: str = DEFAULT_SERVICE_HOST,
        port: int = DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
    ) -> dict[str, Any]:
        """Create minimal config + auth.providers entries."""
        if providers is None:
            providers = ["codex", "copilot"]

        config = ConfigFactory.minimal()
        config["auth"] = {"providers": {}}
        for provider in providers:
            config["auth"]["providers"][provider] = ConfigFactory.auth_provider(
                provider, host=host, port=port
            )
        return config

    @staticmethod
    def with_secret_files(secret_files: list[str]) -> dict[str, Any]:
        """Create minimal config + secret_files list."""
        config = ConfigFactory.minimal()
        config["secret_files"] = copy.deepcopy(secret_files)
        return config

    @staticmethod
    def service(
        name: str,
        port: int,
        *,
        host: str = DEFAULT_SERVICE_HOST,
        readiness_path: str = DEFAULT_READINESS_PATH,
        command_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a generic service dict for validator tests."""
        if command_args is None:
            command_args = ["python", "-c", "import time; time.sleep(60)"]

        return {
            "command": {"args": copy.deepcopy(command_args)},
            "host": host,
            "port": port,
            "readiness_path": readiness_path,
        }
