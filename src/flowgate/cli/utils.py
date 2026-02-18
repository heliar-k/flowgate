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


def _resolve_path(base_dir: Path, value: str) -> str:
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base_dir / p).resolve())


def _resolve_config_paths(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    cfg = json.loads(json.dumps(config))
    base_dir = config_path.parent

    for key, value in cfg["paths"].items():
        if isinstance(value, str):
            cfg["paths"][key] = _resolve_path(base_dir, value)

    cfg["secret_files"] = [
        _resolve_path(base_dir, p) for p in cfg.get("secret_files", [])
    ]

    credentials = cfg.get("credentials", {})
    if isinstance(credentials, dict):
        upstream = credentials.get("upstream", {})
        if isinstance(upstream, dict):
            for entry in upstream.values():
                if not isinstance(entry, dict):
                    continue
                file_path = entry.get("file")
                if isinstance(file_path, str):
                    entry["file"] = _resolve_path(base_dir, file_path)

    for service in cfg.get("services", {}).values():
        command = service.get("command", {})
        cwd = command.get("cwd")
        if isinstance(cwd, str):
            command["cwd"] = _resolve_path(base_dir, cwd)

    return cfg


def _load_and_resolve_config(path: str) -> dict[str, Any]:
    cfg_path = Path(path)
    cfg = load_router_config(cfg_path)
    resolved = _resolve_config_paths(cfg, cfg_path)
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
