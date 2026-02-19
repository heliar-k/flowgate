from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from flowgate.validators import ConfigValidator


class ConfigError(ValueError):
    """Raised when router tool config is invalid."""


_ALLOWED_TOP_LEVEL_KEYS = {
    "config_version",
    "paths",
    "services",
    "credentials",
    "litellm_base",
    "profiles",
    "auth",
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




def _normalize_credentials(credentials: dict[str, Any]) -> dict[str, Any]:
    ConfigValidator.validate_credentials(credentials)

    upstream = credentials.get("upstream", {})
    normalized_upstream: dict[str, dict[str, str]] = {}
    for name, entry in upstream.items():
        file_path = entry.get("file")
        normalized_upstream[name] = {"file": file_path}

    return {"upstream": normalized_upstream}


def _normalize_legacy_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)

    version_raw = normalized.get("config_version", _LATEST_CONFIG_VERSION)
    if not isinstance(version_raw, int):
        raise ConfigError("config_version must be an integer")
    if version_raw not in _SUPPORTED_CONFIG_VERSIONS:
        versions = ", ".join(str(v) for v in sorted(_SUPPORTED_CONFIG_VERSIONS))
        raise ConfigError(
            f"Unsupported config_version={version_raw}; supported versions: {versions}"
        )
    normalized["config_version"] = version_raw

    # Track legacy fields for deprecation warning
    legacy_fields_detected = []

    if "secret_files" not in normalized and "secrets" in normalized:
        normalized["secret_files"] = normalized["secrets"]
        legacy_fields_detected.append("'secrets' → use 'secret_files' instead")
    normalized.pop("secrets", None)

    services_raw = normalized.get("services")
    if isinstance(services_raw, dict):
        services = dict(services_raw)
        if "cliproxyapi_plus" not in services and "cliproxyapi" in services:
            services["cliproxyapi_plus"] = services.pop("cliproxyapi")
            legacy_fields_detected.append("'cliproxyapi' → use 'cliproxyapi_plus' instead")
        normalized["services"] = services

    auth_raw = normalized.get("auth")
    oauth_raw = normalized.get("oauth")

    if "auth" not in normalized and isinstance(oauth_raw, dict):
        normalized["auth"] = {"providers": dict(oauth_raw)}
        legacy_fields_detected.append("'oauth' → use 'auth.providers' instead")
    elif isinstance(auth_raw, dict):
        providers_raw = auth_raw.get("providers", {})
        providers = _ensure_mapping(providers_raw, "auth.providers")
        normalized["auth"] = {"providers": providers}
        if "oauth" not in normalized:
            normalized["oauth"] = dict(providers)

    # Print deprecation warning for config_version 1
    if version_raw == 1:
        warning_lines = [
            "⚠️  WARNING: config_version 1 is deprecated and will be removed in v0.3.0",
            "Please migrate your configuration to version 2.",
            "Run: flowgate config migrate --to-version 2",
            "",
        ]

        if legacy_fields_detected:
            warning_lines.append("Legacy field mappings detected:")
            for field in legacy_fields_detected:
                warning_lines.append(f"- {field}")

        warning_message = "\n".join(warning_lines) + "\n"
        sys.stderr.write(warning_message)

    return normalized


def load_router_config(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    data = _normalize_legacy_fields(_parse_yaml_like(path_obj))

    # Filter out comment fields (keys starting with _comment)
    unknown = sorted(
        k for k in set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS
        if not k.startswith("_comment")
    )
    if unknown:
        raise ConfigError(f"Unknown top-level keys: {', '.join(unknown)}")

    missing = sorted(_REQUIRED_TOP_LEVEL_KEYS - set(data.keys()))
    if missing:
        raise ConfigError(f"Missing required top-level keys: {', '.join(missing)}")

    paths = _ensure_mapping(data["paths"], "paths")
    services = _ensure_mapping(data["services"], "services")
    litellm_base = _ensure_mapping(data["litellm_base"], "litellm_base")
    profiles = _ensure_mapping(data["profiles"], "profiles")

    ConfigValidator.validate_paths(paths)
    ConfigValidator.validate_services(services)
    ConfigValidator.validate_litellm_base(litellm_base)
    ConfigValidator.validate_profiles(profiles)

    credentials_raw = data.get("credentials", {})
    credentials_map = _ensure_mapping(credentials_raw, "credentials")
    credentials = _normalize_credentials(credentials_map)

    oauth = data.get("oauth", {})
    oauth_map = _ensure_mapping(oauth, "oauth")
    ConfigValidator.validate_oauth(oauth_map)

    auth_raw = data.get("auth", {})
    auth_map = _ensure_mapping(auth_raw, "auth")
    providers_raw = auth_map.get("providers", {})
    providers = _ensure_mapping(providers_raw, "auth.providers")
    ConfigValidator.validate_auth_providers(providers)

    secret_files = data.get("secret_files", [])
    ConfigValidator.validate_secret_files(secret_files)

    return {
        "config_version": data["config_version"],
        "paths": paths,
        "services": services,
        "credentials": credentials,
        "litellm_base": litellm_base,
        "profiles": profiles,
        "auth": {"providers": providers},
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
