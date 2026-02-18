from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

import yaml


def detect_cliproxy_config_path(
    config: Mapping[str, Any], config_path: Path
) -> Path | None:
    service = config.get("services", {}).get("cliproxyapi_plus", {})
    command = service.get("command", {})
    args = command.get("args", [])
    cwd_raw = command.get("cwd") or "."
    cwd = Path(str(cwd_raw))
    if not cwd.is_absolute():
        cwd = (Path.cwd() / cwd).resolve()

    cliproxy_cfg: Path | None = None
    if isinstance(args, list):
        for i, item in enumerate(args):
            if item == "-config" and i + 1 < len(args):
                cliproxy_cfg = Path(str(args[i + 1]))
                break

    if cliproxy_cfg is None:
        fallback = config_path.resolve().parent / "cliproxyapi.yaml"
        return fallback if fallback.exists() else None

    if cliproxy_cfg.is_absolute():
        return cliproxy_cfg
    return (cwd / cliproxy_cfg).resolve()


def management_api_url_from_auth(
    config: Mapping[str, Any], host: str, port: int | str
) -> str:
    providers = config.get("auth", {}).get("providers", {})
    if isinstance(providers, dict):
        for provider in providers.values():
            if not isinstance(provider, dict):
                continue
            endpoint = provider.get("auth_url_endpoint")
            if not isinstance(endpoint, str) or not endpoint:
                continue

            parts = urlsplit(endpoint)
            path = parts.path
            marker = "/oauth/"
            idx = path.find(marker)
            if idx != -1:
                base_path = path[:idx].rstrip("/")
            else:
                base_path = path.rsplit("/", 1)[0].rstrip("/")
            if not base_path:
                base_path = "/management.html"
            return urlunsplit((parts.scheme, parts.netloc, base_path, "", ""))

    return f"http://{host}:{port}/management.html"


def management_page_url(host: str, port: int | str) -> str:
    return f"http://{host}:{port}/"


def read_cliproxy_api_keys(cliproxy_cfg_path: Path | None) -> list[str]:
    if cliproxy_cfg_path is None or not cliproxy_cfg_path.exists():
        return []

    try:
        data = yaml.safe_load(cliproxy_cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []

    keys = data.get("api-keys")
    if not isinstance(keys, list):
        return []
    return [str(key) for key in keys if isinstance(key, str) and key.strip()]
