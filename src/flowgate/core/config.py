"""FlowGate configuration loading, path resolution, and validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from flowgate.constants import DEFAULT_READINESS_PATH, DEFAULT_SERVICE_HOST
from flowgate.observability import measure_time


# ── Exceptions ────────────────────────────────────────────────

class ConfigError(ValueError):
    """Raised when router tool config is invalid."""


# ── Path Resolution ───────────────────────────────────────────

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
            - Tilde (~) is expanded to user home directory

        Examples:
            >>> resolver = PathResolver(Path("/etc/flowgate/config.yaml"))
            >>> resolver.resolve("/var/log/app.log")
            '/var/log/app.log'
            >>> resolver.resolve("logs/app.log")
            '/etc/flowgate/logs/app.log'
        """
        p = Path(path_str).expanduser()
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
            1. paths.* - Top-level path fields (runtime_dir, log_file, etc.)
            2. secret_files - List of secret file paths
            3. services.*.command.cwd - Optional service working directories
            4. cliproxyapi_plus.config_file - CLIProxyAPIPlus config path

        Examples:
            >>> resolver = PathResolver(Path("/etc/flowgate/config.yaml"))
            >>> config = {
            ...     "paths": {"runtime_dir": ".router"},
            ...     "secret_files": ["secrets/api.key"],
            ...     "services": {
            ...         "cliproxyapi_plus": {
            ...             "command": {"cwd": "runtime"}
            ...         }
            ...     }
            ... }
            >>> resolved = resolver.resolve_config_paths(config)
            >>> resolved["paths"]["runtime_dir"]
            '/etc/flowgate/.router'
        """
        cfg = copy.deepcopy(config)

        for key, value in cfg["paths"].items():
            if isinstance(value, str):
                cfg["paths"][key] = self.resolve(value)

        cfg["secret_files"] = [self.resolve(p) for p in cfg.get("secret_files", [])]

        for service in cfg.get("services", {}).values():
            command = service.get("command", {})
            cwd = command.get("cwd")
            if isinstance(cwd, str):
                command["cwd"] = self.resolve(cwd)

        cliproxy = cfg.get("cliproxyapi_plus", {})
        if isinstance(cliproxy, dict):
            config_file = cliproxy.get("config_file")
            if isinstance(config_file, str):
                cliproxy["config_file"] = self.resolve(config_file)

        return cfg


# ── Config Loading ────────────────────────────────────────────

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


# ── Validation ────────────────────────────────────────────────

class ConfigValidator:
    """Centralized configuration validation for FlowGate.

    All methods are static and raise ConfigError on validation failures.
    """

    @staticmethod
    def _require_keys(config: dict[str, Any], required: set[str], context: str) -> None:
        missing = sorted(required - set(config.keys()))
        if missing:
            raise ConfigError(
                f"{context} is missing required keys: {', '.join(missing)}"
            )

    @staticmethod
    def _validate_type(value: Any, expected_type: type, name: str) -> None:
        if not isinstance(value, expected_type):
            type_name = expected_type.__name__
            raise ConfigError(f"{name} must be a {type_name}")

    @staticmethod
    def _validate_non_empty_string(value: Any, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{name} must be a non-empty string")

    @staticmethod
    def validate_paths(paths_config: dict[str, Any]) -> None:
        """Validate the paths configuration section.

        Required keys (config_version 3): runtime_dir, log_file

        Args:
            paths_config: The paths section from configuration

        Raises:
            ConfigError: If validation fails
        """
        required = {"runtime_dir", "log_file"}
        ConfigValidator._require_keys(paths_config, required, "paths")

    @staticmethod
    def validate_service(service_name: str, service_config: dict[str, Any]) -> None:
        """Validate a single service configuration.

        Required structure:
        - command: dict with 'args' key
        - command.args: non-empty list of strings

        Optional fields:
        - host: non-empty string
        - port: integer between 1 and 65535
        - readiness_path: non-empty string

        Args:
            service_name: Name of the service (e.g., "cliproxyapi_plus")
            service_config: Service configuration dictionary

        Raises:
            ConfigError: If validation fails
        """
        ConfigValidator._validate_type(service_config, dict, f"services.{service_name}")

        if "command" not in service_config or not isinstance(
            service_config["command"], dict
        ):
            raise ConfigError(f"services.{service_name}.command must be provided")

        args = service_config["command"].get("args")
        if (
            not isinstance(args, list)
            or not all(isinstance(i, str) for i in args)
            or not args
        ):
            raise ConfigError(
                f"services.{service_name}.command.args must be a non-empty string list"
            )

        host = service_config.get("host")
        if host is not None:
            ConfigValidator._validate_non_empty_string(
                host, f"services.{service_name}.host"
            )

        port = service_config.get("port")
        if port is not None:
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ConfigError(
                    f"services.{service_name}.port must be an integer between 1 and 65535"
                )

        readiness_path = service_config.get("readiness_path")
        if readiness_path is not None:
            ConfigValidator._validate_non_empty_string(
                readiness_path, f"services.{service_name}.readiness_path"
            )

    @staticmethod
    def validate_services(services_config: dict[str, Any]) -> None:
        """Validate the services configuration section.

        Required services (config_version 3): cliproxyapi_plus
        Each service must have valid command configuration.

        Args:
            services_config: The services section from configuration

        Raises:
            ConfigError: If validation fails
        """
        required = {"cliproxyapi_plus"}
        ConfigValidator._require_keys(services_config, required, "services")

        for name, svc in services_config.items():
            if name.startswith("_comment"):
                continue
            ConfigValidator.validate_service(name, svc)

    @staticmethod
    def validate_auth_providers(providers_config: dict[str, Any]) -> None:
        """Validate the auth.providers configuration section.

        Each provider must be a dictionary. If auth_url_endpoint or status_endpoint
        are provided, they must be non-empty strings.

        Args:
            providers_config: The auth.providers section from configuration

        Raises:
            ConfigError: If validation fails
        """
        for name, provider in providers_config.items():
            ConfigValidator._validate_type(provider, dict, f"auth.providers.{name}")

            auth_url = provider.get("auth_url_endpoint")
            if auth_url is not None:
                ConfigValidator._validate_non_empty_string(
                    auth_url, f"auth.providers.{name}.auth_url_endpoint"
                )

            status_url = provider.get("status_endpoint")
            if status_url is not None:
                ConfigValidator._validate_non_empty_string(
                    status_url, f"auth.providers.{name}.status_endpoint"
                )

    @staticmethod
    def validate_secret_files(secret_files: Any) -> None:
        """Validate the secret_files configuration.

        Must be a list of string paths.

        Args:
            secret_files: The secret_files value from configuration

        Raises:
            ConfigError: If validation fails
        """
        if not isinstance(secret_files, list) or not all(
            isinstance(p, str) for p in secret_files
        ):
            raise ConfigError("secret_files must be a list of string paths")
