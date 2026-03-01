"""
Utility functions for CLI operations.

This module contains helper functions for configuration loading,
path resolution, and common CLI operations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TextIO

from ..config import load_router_config
from ..config_utils.path_resolver import PathResolver


def _load_and_resolve_config(path: str) -> dict[str, Any]:
    cfg_path = Path(path)
    cfg = load_router_config(cfg_path)

    resolver = PathResolver(cfg_path)
    resolved = resolver.resolve_config_paths(cfg)

    resolved["_meta"] = {
        "config_path": str(cfg_path.resolve()),
        "config_dir": str(cfg_path.resolve().parent),
    }
    return resolved


def _default_auth_dir(config: dict[str, Any]) -> str:
    runtime_dir = config.get("paths", {}).get("runtime_dir")
    if isinstance(runtime_dir, str) and runtime_dir:
        return str((Path(runtime_dir).resolve().parent / "auths").resolve())

    config_dir = Path(config.get("_meta", {}).get("config_dir", os.getcwd()))
    return str((config_dir / "auths").resolve())


def effective_secret_files(config: dict[str, Any]) -> list[str]:
    """Collect all secret files from config and auth directory."""
    paths: set[str] = set()
    for value in config.get("secret_files", []):
        if isinstance(value, str) and value.strip():
            paths.add(str(Path(value).resolve()))

    default_auth_dir = Path(_default_auth_dir(config))
    if default_auth_dir.exists():
        for item in default_auth_dir.glob("*.json"):
            paths.add(str(item.resolve()))

    return sorted(paths)


def maybe_print_update_notification(config: dict[str, Any], *, stdout: TextIO) -> None:
    """Print CLIProxyAPIPlus update notification if available (TTY only)."""
    from ..bootstrap import DEFAULT_CLIPROXY_REPO, DEFAULT_CLIPROXY_VERSION
    from ..cliproxyapiplus import (
        check_update,
        read_installed_version,
    )

    isatty = getattr(stdout, "isatty", None)
    if callable(isatty) and not isatty():
        return

    runtime_dir = str(config.get("paths", {}).get("runtime_dir", "")).strip()
    if not runtime_dir:
        return

    current_version = read_installed_version(
        runtime_dir, DEFAULT_CLIPROXY_VERSION
    )
    update = check_update(
        runtime_dir=runtime_dir,
        current_version=current_version,
        repo=DEFAULT_CLIPROXY_REPO,
    )
    if not update:
        return

    latest = update["latest_version"]
    release_url = update.get("release_url", "")
    config_path = str(
        config.get("_meta", {}).get("config_path", "config/flowgate.yaml")
    )
    print(
        (
            "cliproxyapi_plus:update_available "
            f"current={current_version} latest={latest} "
            f"release={release_url if release_url else 'n/a'}"
        ),
        file=stdout,
    )
    print(
        (
            "cliproxyapi_plus:update_suggestion "
            "command="
            f"'uv run flowgate --config {config_path} "
            f"bootstrap update'"
        ),
        file=stdout,
    )
