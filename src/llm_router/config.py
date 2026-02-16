from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when router tool config is invalid."""


_ALLOWED_TOP_LEVEL_KEYS = {
    "config_version",
    "paths",
    "services",
    "litellm_base",
    "profiles",
    "oauth",
    "secret_files",
}

_REQUIRED_TOP_LEVEL_KEYS = {
    "paths",
    "services",
    "litellm_base",
    "profiles",
}

_LATEST_CONFIG_VERSION = 2
_SUPPORTED_CONFIG_VERSIONS = {1, 2}


def _parse_yaml_like(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except ModuleNotFoundError:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(
                "PyYAML is not installed and config is not valid JSON (JSON is valid YAML subset)."
            ) from exc

    if not isinstance(data, dict):
        raise ConfigError("Top-level config must be a mapping/object.")
    return data


def _ensure_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a mapping/object")
    return value


def _validate_paths(paths: dict[str, Any]) -> None:
    required = {"runtime_dir", "active_config", "state_file", "log_file"}
    missing = sorted(required - set(paths.keys()))
    if missing:
        raise ConfigError(f"paths is missing required keys: {', '.join(missing)}")


def _validate_services(services: dict[str, Any]) -> None:
    required = {"litellm", "cliproxyapi_plus"}
    missing = sorted(required - set(services.keys()))
    if missing:
        raise ConfigError(f"services is missing required keys: {', '.join(missing)}")

    for name, svc in services.items():
        if not isinstance(svc, dict):
            raise ConfigError(f"services.{name} must be a mapping/object")
        if "command" not in svc or not isinstance(svc["command"], dict):
            raise ConfigError(f"services.{name}.command must be provided")
        args = svc["command"].get("args")
        if not isinstance(args, list) or not all(isinstance(i, str) for i in args) or not args:
            raise ConfigError(f"services.{name}.command.args must be a non-empty string list")


def _validate_profiles(profiles: dict[str, Any]) -> None:
    if not profiles:
        raise ConfigError("profiles must not be empty")
    for key, value in profiles.items():
        if not isinstance(key, str) or not key:
            raise ConfigError("profile names must be non-empty strings")
        if not isinstance(value, dict):
            raise ConfigError(f"profiles.{key} must be a mapping/object")


def _validate_oauth(oauth: dict[str, Any]) -> None:
    for name, provider in oauth.items():
        if not isinstance(provider, dict):
            raise ConfigError(f"oauth.{name} must be a mapping/object")


def _normalize_legacy_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)

    version_raw = normalized.get("config_version", _LATEST_CONFIG_VERSION)
    if not isinstance(version_raw, int):
        raise ConfigError("config_version must be an integer")
    if version_raw not in _SUPPORTED_CONFIG_VERSIONS:
        versions = ", ".join(str(v) for v in sorted(_SUPPORTED_CONFIG_VERSIONS))
        raise ConfigError(f"Unsupported config_version={version_raw}; supported versions: {versions}")
    normalized["config_version"] = version_raw

    if "secret_files" not in normalized and "secrets" in normalized:
        normalized["secret_files"] = normalized["secrets"]
    normalized.pop("secrets", None)

    services_raw = normalized.get("services")
    if isinstance(services_raw, dict):
        services = dict(services_raw)
        if "cliproxyapi_plus" not in services and "cliproxyapi" in services:
            services["cliproxyapi_plus"] = services.pop("cliproxyapi")
        normalized["services"] = services

    return normalized


def load_router_config(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    data = _normalize_legacy_fields(_parse_yaml_like(path_obj))

    unknown = sorted(set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        raise ConfigError(f"Unknown top-level keys: {', '.join(unknown)}")

    missing = sorted(_REQUIRED_TOP_LEVEL_KEYS - set(data.keys()))
    if missing:
        raise ConfigError(f"Missing required top-level keys: {', '.join(missing)}")

    paths = _ensure_mapping(data["paths"], "paths")
    services = _ensure_mapping(data["services"], "services")
    litellm_base = _ensure_mapping(data["litellm_base"], "litellm_base")
    profiles = _ensure_mapping(data["profiles"], "profiles")

    _validate_paths(paths)
    _validate_services(services)
    _validate_profiles(profiles)

    oauth = data.get("oauth", {})
    oauth_map = _ensure_mapping(oauth, "oauth")
    _validate_oauth(oauth_map)

    secret_files = data.get("secret_files", [])
    if not isinstance(secret_files, list) or not all(isinstance(p, str) for p in secret_files):
        raise ConfigError("secret_files must be a list of string paths")

    return {
        "config_version": data["config_version"],
        "paths": paths,
        "services": services,
        "litellm_base": litellm_base,
        "profiles": profiles,
        "oauth": oauth_map,
        "secret_files": secret_files,
    }


def merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, dict):
            result[key] = merge_dicts(value, {})
        elif isinstance(value, list):
            result[key] = list(value)
        else:
            result[key] = value

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        elif isinstance(value, list):
            result[key] = list(value)
        else:
            result[key] = value
    return result
