from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flowgate.observability import measure_time
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
    "secret_files",
}

_REQUIRED_TOP_LEVEL_KEYS = {
    "paths",
    "services",
    "litellm_base",
    "profiles",
}

_LATEST_CONFIG_VERSION = 2
_SUPPORTED_CONFIG_VERSIONS = {2}


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


def _validate_api_key_refs(config: dict[str, Any]) -> None:
    """Validate that all api_key_ref values reference existing credentials.

    Scans litellm_base.model_list and all profiles.*.model_list for api_key_ref
    and ensures each reference exists in credentials.upstream.
    """
    credentials = config.get("credentials", {})
    upstream = credentials.get("upstream", {})
    available_refs = set(upstream.keys())

    refs_to_check: list[tuple[str, str]] = []  # (ref, location)

    # Scan litellm_base.model_list
    litellm_base = config.get("litellm_base", {})
    model_list = litellm_base.get("model_list", [])
    if isinstance(model_list, list):
        for idx, model in enumerate(model_list):
            if not isinstance(model, dict):
                continue
            params = model.get("litellm_params", {})
            if not isinstance(params, dict):
                continue
            ref = params.get("api_key_ref")
            if ref:
                refs_to_check.append((ref, f"litellm_base.model_list[{idx}]"))

    # Scan profiles.*.model_list
    profiles = config.get("profiles", {})
    if isinstance(profiles, dict):
        for profile_name, profile_config in profiles.items():
            if not isinstance(profile_config, dict):
                continue
            profile_model_list = profile_config.get("model_list", [])
            if isinstance(profile_model_list, list):
                for idx, model in enumerate(profile_model_list):
                    if not isinstance(model, dict):
                        continue
                    params = model.get("litellm_params", {})
                    if not isinstance(params, dict):
                        continue
                    ref = params.get("api_key_ref")
                    if ref:
                        refs_to_check.append(
                            (ref, f"profiles.{profile_name}.model_list[{idx}]")
                        )

    # Check all references
    invalid_refs = []
    for ref, location in refs_to_check:
        if ref not in available_refs:
            invalid_refs.append(f"{location}.litellm_params.api_key_ref='{ref}'")

    if invalid_refs:
        raise ConfigError(
            f"Invalid api_key_ref values (not found in credentials.upstream): "
            f"{', '.join(invalid_refs)}"
        )


@measure_time("config_normalize")
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

    auth_raw = normalized.get("auth")
    if isinstance(auth_raw, dict):
        providers_raw = auth_raw.get("providers", {})
        providers = _ensure_mapping(providers_raw, "auth.providers")
        normalized["auth"] = {"providers": providers}

    return normalized


@measure_time("config_load")
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

    auth_raw = data.get("auth", {})
    auth_map = _ensure_mapping(auth_raw, "auth")
    providers_raw = auth_map.get("providers", {})
    providers = _ensure_mapping(providers_raw, "auth.providers")
    ConfigValidator.validate_auth_providers(providers)

    secret_files = data.get("secret_files", [])
    ConfigValidator.validate_secret_files(secret_files)

    # Validate api_key_ref cross-references
    _validate_api_key_refs(data)

    return {
        "config_version": data["config_version"],
        "paths": paths,
        "services": services,
        "credentials": credentials,
        "litellm_base": litellm_base,
        "profiles": profiles,
        "auth": {"providers": providers},
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
