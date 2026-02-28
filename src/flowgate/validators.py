"""Configuration validation utilities for FlowGate.

This module provides centralized validation logic for configuration files,
extracting validation concerns from the main config module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowgate.config import ConfigError


class ConfigValidator:
    """Centralized configuration validation for FlowGate.

    All methods are static and raise ConfigError on validation failures.
    """

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _require_keys(config: dict[str, Any], required: set[str], context: str) -> None:
        """Check that all required keys exist in config.

        Args:
            config: Configuration dictionary to validate
            required: Set of required key names
            context: Context string for error messages (e.g., "paths", "services")

        Raises:
            ConfigError: If any required keys are missing
        """
        from flowgate.config import ConfigError

        missing = sorted(required - set(config.keys()))
        if missing:
            raise ConfigError(
                f"{context} is missing required keys: {', '.join(missing)}"
            )

    @staticmethod
    def _validate_type(value: Any, expected_type: type, name: str) -> None:
        """Validate that a value matches the expected type.

        Args:
            value: Value to validate
            expected_type: Expected Python type
            name: Field name for error messages

        Raises:
            ConfigError: If value type doesn't match expected type
        """
        from flowgate.config import ConfigError

        if not isinstance(value, expected_type):
            type_name = expected_type.__name__
            raise ConfigError(f"{name} must be a {type_name}")

    @staticmethod
    def _validate_non_empty_string(value: Any, name: str) -> None:
        """Validate that a value is a non-empty string.

        Args:
            value: Value to validate
            name: Field name for error messages

        Raises:
            ConfigError: If value is not a string or is empty
        """
        from flowgate.config import ConfigError

        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{name} must be a non-empty string")

    # -------------------------------------------------------------------------
    # Validator Methods
    # -------------------------------------------------------------------------

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
        from flowgate.config import ConfigError

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

        # Validate host (optional field)
        host = service_config.get("host")
        if host is not None:
            ConfigValidator._validate_non_empty_string(
                host, f"services.{service_name}.host"
            )

        # Validate port (optional field)
        port = service_config.get("port")
        if port is not None:
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise ConfigError(
                    f"services.{service_name}.port must be an integer between 1 and 65535"
                )

        # Validate readiness_path (optional field)
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
            # Skip comment fields
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

            # Validate auth_url_endpoint (optional)
            auth_url = provider.get("auth_url_endpoint")
            if auth_url is not None:
                ConfigValidator._validate_non_empty_string(
                    auth_url, f"auth.providers.{name}.auth_url_endpoint"
                )

            # Validate status_endpoint (optional)
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
        from flowgate.config import ConfigError

        if not isinstance(secret_files, list) or not all(
            isinstance(p, str) for p in secret_files
        ):
            raise ConfigError("secret_files must be a list of string paths")

    @staticmethod
    def validate_integration(integration_config: dict[str, Any]) -> None:
        """Validate the integration configuration section.

        Supported keys:
        - default_model: non-empty string (optional)
        - fast_model: non-empty string (optional)

        Args:
            integration_config: The integration section from configuration

        Raises:
            ConfigError: If validation fails
        """
        from flowgate.config import ConfigError

        unknown = sorted(
            k
            for k in set(integration_config.keys()) - {"default_model", "fast_model"}
            if not str(k).startswith("_comment")
        )
        if unknown:
            raise ConfigError(f"integration has unknown keys: {', '.join(unknown)}")

        default_model = integration_config.get("default_model")
        if default_model is not None:
            ConfigValidator._validate_non_empty_string(
                default_model, "integration.default_model"
            )

        fast_model = integration_config.get("fast_model")
        if fast_model is not None:
            ConfigValidator._validate_non_empty_string(
                fast_model, "integration.fast_model"
            )
