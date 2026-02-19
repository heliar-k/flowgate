"""
Utility functions for CLI operations.

This module contains helper functions for configuration loading,
path resolution, and common CLI operations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..config import load_router_config
from ..config_utils.path_resolver import PathResolver


def _load_and_resolve_config(path: str) -> dict[str, Any]:
    cfg_path = Path(path)
    cfg = load_router_config(cfg_path)

    # Use PathResolver to resolve all configuration paths
    resolver = PathResolver(cfg_path)
    resolved = resolver.resolve_config_paths(cfg)

    resolved["_meta"] = {
        "config_path": str(cfg_path.resolve()),
        "config_dir": str(cfg_path.resolve().parent),
    }
    return resolved


def _read_state_file(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _default_auth_dir(config: dict[str, Any]) -> str:
    runtime_dir = config.get("paths", {}).get("runtime_dir")
    if isinstance(runtime_dir, str) and runtime_dir:
        return str((Path(runtime_dir).resolve().parent / "auths").resolve())

    config_dir = Path(config.get("_meta", {}).get("config_dir", os.getcwd()))
    return str((config_dir / "auths").resolve())
