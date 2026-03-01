from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flowgate.constants import DEFAULT_READINESS_PATH, DEFAULT_SERVICE_HOST
from flowgate.observability import measure_time
from flowgate.validators import ConfigValidator


class ConfigError(ValueError):
    """Raised when router tool config is invalid."""


_ALLOWED_TOP_LEVEL_KEYS = {
    "config_version",
    "paths",
    "cliproxyapi_plus",
    "auth",
    "secret_files",
}

_REQUIRED_TOP_LEVEL_KEYS = {
    "paths",
    "cliproxyapi_plus",
}

_LATEST_CONFIG_VERSION = 3
_SUPPORTED_CONFIG_VERSIONS = {3}


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


def _resolve_path_relative_to_config(config_path: Path, raw: str) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return (config_path.parent / p).resolve()


def _derive_cliproxy_service(
    *,
    flowgate_config_path: Path,
    paths: dict[str, Any],
    cliproxy_section: dict[str, Any],
) -> tuple[dict[str, Any], Path]:
    config_file_raw = cliproxy_section.get("config_file")
    if not isinstance(config_file_raw, str) or not config_file_raw.strip():
        raise ConfigError("cliproxyapi_plus.config_file must be a non-empty string")

    cliproxy_cfg_path = _resolve_path_relative_to_config(
        flowgate_config_path, config_file_raw.strip()
    )
    cliproxy_cfg = _parse_yaml_like(cliproxy_cfg_path)

    host_raw = cliproxy_cfg.get("host", DEFAULT_SERVICE_HOST)
    host = str(host_raw).strip() if host_raw is not None else DEFAULT_SERVICE_HOST
    if not host:
        host = DEFAULT_SERVICE_HOST

    port = cliproxy_cfg.get("port")
    if not isinstance(port, int):
        raise ConfigError("CLIProxyAPIPlus config 'port' must be an integer")

    runtime_dir = paths.get("runtime_dir")
    if not isinstance(runtime_dir, str) or not runtime_dir.strip():
        raise ConfigError("paths.runtime_dir must be a non-empty string")
    runtime_dir_path = _resolve_path_relative_to_config(
        flowgate_config_path, runtime_dir.strip()
    )

    project_root = flowgate_config_path.parent.resolve().parent
    binary = str(runtime_dir_path / "bin" / "CLIProxyAPIPlus")

    service = {
        "host": host,
        "port": port,
        "readiness_path": DEFAULT_READINESS_PATH,
        "command": {
            "cwd": str(project_root),
            "args": [binary, "-config", str(cliproxy_cfg_path)],
        },
    }
    return service, cliproxy_cfg_path


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
        k
        for k in set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS
        if not k.startswith("_comment")
    )
    if unknown:
        raise ConfigError(f"Unknown top-level keys: {', '.join(unknown)}")

    missing = sorted(_REQUIRED_TOP_LEVEL_KEYS - set(data.keys()))
    if missing:
        raise ConfigError(f"Missing required top-level keys: {', '.join(missing)}")

    paths = _ensure_mapping(data["paths"], "paths")
    ConfigValidator.validate_paths(paths)

    cliproxy_section = _ensure_mapping(data["cliproxyapi_plus"], "cliproxyapi_plus")
    cliproxy_service, cliproxy_cfg_path = _derive_cliproxy_service(
        flowgate_config_path=path_obj,
        paths=paths,
        cliproxy_section=cliproxy_section,
    )
    services = {"cliproxyapi_plus": cliproxy_service}
    ConfigValidator.validate_services(services)

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
        "cliproxyapi_plus": {"config_file": str(cliproxy_cfg_path)},
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
