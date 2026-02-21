"""Test configuration data factory.

This module provides factory methods to create test configurations,
eliminating hardcoded config duplication across test files.
"""

import copy
from typing import Any, Dict, List, Optional

from flowgate.constants import (
    DEFAULT_READINESS_PATH,
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORTS,
    DEFAULT_SERVICE_READINESS_PATHS,
)


class ConfigFactory:
    """Factory for creating test configuration data.

    All factory methods return mutable dictionaries that can be modified
    by test cases for specific scenarios.
    """

    @staticmethod
    def minimal() -> Dict[str, Any]:
        """Create minimal valid configuration.

        This is the baseline config that satisfies all required schema fields.
        Use this as the starting point for most tests.

        Returns:
            dict: Minimal valid config with config_version 2 (implicit default)
        """
        return {
            "paths": {
                "runtime_dir": ".router",
                "active_config": ".router/runtime/active_config.yaml",
                "state_file": ".router/runtime/state.json",
                "log_file": ".router/runtime/events.log",
            },
            "services": {
                "litellm": ConfigFactory.service("litellm", DEFAULT_SERVICE_PORTS["litellm"]),
                "cliproxyapi_plus": ConfigFactory.service(
                    "cliproxyapi", DEFAULT_SERVICE_PORTS["cliproxyapi_plus"]
                ),
            },
            "litellm_base": ConfigFactory.litellm_base_minimal(),
            "profiles": {"default": {}},
        }

    @staticmethod
    def with_config_version(version: int) -> Dict[str, Any]:
        """Create config with explicit config_version.

        Args:
            version: Config schema version (1 or 2)

        Returns:
            dict: Config with explicit version set
        """
        config = ConfigFactory.minimal()
        config["config_version"] = version
        return config

    @staticmethod
    def with_auth(providers: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create config with auth providers.

        Args:
            providers: List of provider names (default: ["codex", "copilot"])

        Returns:
            dict: Config with auth.providers configured
        """
        if providers is None:
            providers = ["codex", "copilot"]

        config = ConfigFactory.minimal()
        config["auth"] = {"providers": {}}
        for provider in providers:
            config["auth"]["providers"][provider] = ConfigFactory.auth_provider(provider)
        return config

    @staticmethod
    def with_credentials(upstream: Dict[str, str]) -> Dict[str, Any]:
        """Create config with upstream credential files.

        Args:
            upstream: Mapping of credential name to file path
                     e.g., {"openai": "/path/to/openai.key"}

        Returns:
            dict: Config with credentials.upstream configured
        """
        config = ConfigFactory.minimal()
        config["credentials"] = {"upstream": {}}
        for name, file_path in upstream.items():
            config["credentials"]["upstream"][name] = {"file": file_path}
        return config

    @staticmethod
    def with_profiles(
        profile_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create config with multiple profiles.

        Args:
            profile_names: List of profile names (default: ["reliability", "balanced", "cost"])

        Returns:
            dict: Config with profiles configured
        """
        if profile_names is None:
            profile_names = ["reliability", "balanced", "cost"]

        config = ConfigFactory.minimal()
        config["profiles"] = {}
        for name in profile_names:
            config["profiles"][name] = ConfigFactory.profile(name)
        return config

    @staticmethod
    def with_secret_files(secret_files: List[str]) -> Dict[str, Any]:
        """Create config with secret_files list.

        Args:
            secret_files: List of paths to secret files

        Returns:
            dict: Config with secret_files configured
        """
        config = ConfigFactory.minimal()
        config["secret_files"] = copy.deepcopy(secret_files)
        return config

    @staticmethod
    def full_featured() -> Dict[str, Any]:
        """Create fully-featured config with all optional sections.

        This includes auth providers, credentials, profiles, and secret files.
        Useful for integration tests.

        Returns:
            dict: Complete config with all features
        """
        config = ConfigFactory.minimal()
        config["auth"] = {
            "providers": {
                "codex": ConfigFactory.auth_provider("codex"),
                "copilot": ConfigFactory.auth_provider("copilot"),
            }
        }
        config["credentials"] = {
            "upstream": {
                "openai": {"file": "secrets/openai.key"},
                "anthropic": {"file": "secrets/anthropic.key"},
            }
        }
        config["profiles"] = {
            "reliability": ConfigFactory.profile("reliability"),
            "balanced": ConfigFactory.profile("balanced"),
            "cost": ConfigFactory.profile("cost"),
        }
        config["secret_files"] = ["auth/codex.json", "auth/copilot.json"]
        return config

    @staticmethod
    def service(
        name: str,
        port: int,
        host: str = DEFAULT_SERVICE_HOST,
        readiness_path: Optional[str] = None,
        command_args: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create service configuration.

        Args:
            name: Service name (used in default command)
            port: Service port
            host: Service host (default: 127.0.0.1)
            readiness_path: Health check path (default: from constants or /health)
            command_args: Command arguments (default: simple sleep command)

        Returns:
            dict: Service configuration
        """
        if readiness_path is None:
            readiness_path = DEFAULT_SERVICE_READINESS_PATHS.get(name, DEFAULT_READINESS_PATH)

        if command_args is None:
            command_args = ["python", "-c", "import time; time.sleep(60)"]

        return {
            "command": {"args": command_args},
            "host": host,
            "port": port,
            "readiness_path": readiness_path,
        }

    @staticmethod
    def litellm_base_minimal() -> Dict[str, Any]:
        """Create minimal litellm_base configuration.

        Returns:
            dict: Minimal litellm_base with one test model
        """
        return {
            "model_list": [
                {
                    "model_name": "router-default",
                    "litellm_params": {
                        "model": "openai/gpt-4o",
                    },
                }
            ],
            "router_settings": {},
            "litellm_settings": {"num_retries": 1},
        }

    @staticmethod
    def litellm_base_with_api_key(api_key: str = "test-api-key") -> Dict[str, Any]:
        """Create litellm_base with hardcoded API key.

        Args:
            api_key: API key value

        Returns:
            dict: litellm_base with api_key in model params
        """
        base = ConfigFactory.litellm_base_minimal()
        base["model_list"][0]["litellm_params"]["api_key"] = api_key
        return base

    @staticmethod
    def litellm_base_with_api_key_ref(ref_name: str) -> Dict[str, Any]:
        """Create litellm_base with api_key_ref.

        Args:
            ref_name: Credential reference name

        Returns:
            dict: litellm_base with api_key_ref in model params
        """
        base = ConfigFactory.litellm_base_minimal()
        base["model_list"][0]["litellm_params"]["api_key_ref"] = ref_name
        return base

    @staticmethod
    def auth_provider(
        provider_name: str,
        method: str = "oauth_poll",
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create auth provider configuration.

        Args:
            provider_name: Provider name (e.g., "codex", "copilot")
            method: Auth method (default: "oauth_poll")
            base_url: Base URL for endpoints (default: http://127.0.0.1:900X)

        Returns:
            dict: Auth provider configuration
        """
        if base_url is None:
            port = 9000 if provider_name == "codex" else 9001
            base_url = f"http://127.0.0.1:{port}"

        return {
            "method": method,
            "auth_url_endpoint": f"{base_url}/auth-url",
            "status_endpoint": f"{base_url}/status",
        }

    @staticmethod
    def profile(
        profile_name: str,
        custom_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create profile configuration.

        Args:
            profile_name: Profile name (determines default retry settings)
            custom_settings: Custom litellm_settings to merge (optional)

        Returns:
            dict: Profile configuration
        """
        # Default retry/cooldown based on profile name
        defaults = {
            "reliability": {"num_retries": 3, "cooldown_time": 60},
            "balanced": {"num_retries": 2, "cooldown_time": 30},
            "cost": {"num_retries": 1, "cooldown_time": 10},
        }

        settings = defaults.get(profile_name, {"num_retries": 1, "cooldown_time": 10})

        if custom_settings:
            settings = {**settings, **custom_settings}

        return {"litellm_settings": settings}

    @staticmethod
    def paths(
        runtime_dir: str = ".router",
        active_config: Optional[str] = None,
        state_file: Optional[str] = None,
        log_file: Optional[str] = None,
    ) -> Dict[str, str]:
        """Create paths configuration.

        Args:
            runtime_dir: Runtime directory path
            active_config: Active config path (auto-derived if None)
            state_file: State file path (auto-derived if None)
            log_file: Log file path (auto-derived if None)

        Returns:
            dict: Paths configuration
        """
        if active_config is None:
            active_config = f"{runtime_dir}/runtime/active_config.yaml"
        if state_file is None:
            state_file = f"{runtime_dir}/runtime/state.json"
        if log_file is None:
            log_file = f"{runtime_dir}/runtime/events.log"

        return {
            "runtime_dir": runtime_dir,
            "active_config": active_config,
            "state_file": state_file,
            "log_file": log_file,
        }
