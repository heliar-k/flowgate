"""Unified path resolution for FlowGate configuration files.

This module provides the PathResolver class for consistent path handling
across all configuration scenarios.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from ..observability import measure_time


class PathResolver:
    """Unified configuration path resolver.

    Resolves relative paths in configuration files relative to the config
    file's directory, while preserving absolute paths unchanged.

    Attributes:
        config_dir: Resolved absolute path to the configuration file's directory
    """

    def __init__(self, config_path: Path) -> None:
        """Initialize path resolver.

        Args:
            config_path: Path to the configuration file
        """
        self.config_dir = config_path.parent.resolve()

    def resolve(self, path_str: str) -> str:
        """Resolve a single path string.

        Args:
            path_str: Path string to resolve

        Returns:
            Resolved absolute path as string

        Resolution rules:
            - Absolute paths: returned unchanged
            - Relative paths: resolved relative to config_dir

        Examples:
            >>> resolver = PathResolver(Path("/etc/flowgate/config.yaml"))
            >>> resolver.resolve("/var/log/app.log")
            '/var/log/app.log'
            >>> resolver.resolve("logs/app.log")
            '/etc/flowgate/logs/app.log'
        """
        p = Path(path_str)
        if p.is_absolute():
            return str(p)
        return str((self.config_dir / p).resolve())

    @measure_time("path_resolution")
    def resolve_config_paths(self, config: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolve all path fields in configuration.

        Creates a deep copy of the configuration and resolves paths in-place.
        Does not modify the original configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            New configuration dictionary with all paths resolved

        Path types handled:
            1. paths.* - Top-level path fields (runtime_dir, active_config, etc.)
            2. secret_files - List of secret file paths
            3. credentials.upstream.*.file - Nested credential file paths
            4. services.*.command.cwd - Optional service working directories

        Examples:
            >>> resolver = PathResolver(Path("/etc/flowgate/config.yaml"))
            >>> config = {
            ...     "paths": {"runtime_dir": ".router"},
            ...     "secret_files": ["secrets/api.key"],
            ...     "credentials": {
            ...         "upstream": {
            ...             "openai": {"file": "creds/openai.key"}
            ...         }
            ...     },
            ...     "services": {
            ...         "litellm": {
            ...             "command": {"cwd": "runtime"}
            ...         }
            ...     }
            ... }
            >>> resolved = resolver.resolve_config_paths(config)
            >>> resolved["paths"]["runtime_dir"]
            '/etc/flowgate/.router'
        """
        # Deep copy to avoid modifying original config
        cfg = copy.deepcopy(config)

        # 1. Resolve paths.* fields
        for key, value in cfg["paths"].items():
            if isinstance(value, str):
                cfg["paths"][key] = self.resolve(value)

        # 2. Resolve secret_files list
        cfg["secret_files"] = [
            self.resolve(p) for p in cfg.get("secret_files", [])
        ]

        # 3. Resolve credentials.upstream.*.file paths
        credentials = cfg.get("credentials", {})
        if isinstance(credentials, dict):
            upstream = credentials.get("upstream", {})
            if isinstance(upstream, dict):
                for entry in upstream.values():
                    if not isinstance(entry, dict):
                        continue
                    file_path = entry.get("file")
                    if isinstance(file_path, str):
                        entry["file"] = self.resolve(file_path)

        # 4. Resolve services.*.command.cwd paths
        for service in cfg.get("services", {}).values():
            command = service.get("command", {})
            cwd = command.get("cwd")
            if isinstance(cwd, str):
                command["cwd"] = self.resolve(cwd)

        return cfg
