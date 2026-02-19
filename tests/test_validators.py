"""Tests for configuration validation utilities."""

import unittest

from flowgate.config import ConfigError
from flowgate.validators import ConfigValidator


class TestConfigValidatorHelpers(unittest.TestCase):
    """Test ConfigValidator helper methods."""

    def test_require_keys_valid(self):
        """Test _require_keys with all required keys present."""
        config = {"key1": "value1", "key2": "value2", "key3": "value3"}
        required = {"key1", "key2"}
        try:
            ConfigValidator._require_keys(config, required, "test_context")
        except ConfigError:
            self.fail("Valid config should not raise ConfigError")

    def test_require_keys_missing_single(self):
        """Test _require_keys with one missing key."""
        config = {"key1": "value1"}
        required = {"key1", "key2"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator._require_keys(config, required, "test_context")
        self.assertIn("test_context is missing required keys: key2", str(ctx.exception))

    def test_require_keys_missing_multiple(self):
        """Test _require_keys with multiple missing keys."""
        config = {"key1": "value1"}
        required = {"key1", "key2", "key3"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator._require_keys(config, required, "test_context")
        error_msg = str(ctx.exception)
        self.assertIn("test_context is missing required keys:", error_msg)
        self.assertIn("key2", error_msg)
        self.assertIn("key3", error_msg)

    def test_validate_type_valid(self):
        """Test _validate_type with correct type."""
        try:
            ConfigValidator._validate_type("string_value", str, "test_field")
            ConfigValidator._validate_type(123, int, "test_field")
            ConfigValidator._validate_type({"key": "value"}, dict, "test_field")
            ConfigValidator._validate_type(["item"], list, "test_field")
        except ConfigError:
            self.fail("Valid types should not raise ConfigError")

    def test_validate_type_invalid(self):
        """Test _validate_type with wrong type."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator._validate_type(123, str, "test_field")
        self.assertIn("test_field must be a str", str(ctx.exception))

    def test_validate_non_empty_string_valid(self):
        """Test _validate_non_empty_string with valid string."""
        try:
            ConfigValidator._validate_non_empty_string("valid", "test_field")
            ConfigValidator._validate_non_empty_string("  valid  ", "test_field")
        except ConfigError:
            self.fail("Valid non-empty string should not raise ConfigError")

    def test_validate_non_empty_string_empty(self):
        """Test _validate_non_empty_string with empty string."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator._validate_non_empty_string("", "test_field")
        self.assertIn("test_field must be a non-empty string", str(ctx.exception))

    def test_validate_non_empty_string_whitespace(self):
        """Test _validate_non_empty_string with whitespace-only string."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator._validate_non_empty_string("   ", "test_field")
        self.assertIn("test_field must be a non-empty string", str(ctx.exception))

    def test_validate_non_empty_string_not_string(self):
        """Test _validate_non_empty_string with non-string value."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator._validate_non_empty_string(123, "test_field")
        self.assertIn("test_field must be a non-empty string", str(ctx.exception))


class TestValidatePaths(unittest.TestCase):
    """Test validate_paths method."""

    def _valid_paths_config(self):
        """Return a valid paths configuration."""
        return {
            "runtime_dir": ".router",
            "active_config": ".router/active.yaml",
            "state_file": ".router/state.json",
            "log_file": ".router/events.log",
        }

    def test_validate_paths_valid(self):
        """Test validate_paths with valid config."""
        config = self._valid_paths_config()
        try:
            ConfigValidator.validate_paths(config)
        except ConfigError:
            self.fail("Valid paths config should not raise ConfigError")

    def test_validate_paths_missing_runtime_dir(self):
        """Test validate_paths with missing runtime_dir."""
        config = self._valid_paths_config()
        del config["runtime_dir"]
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_paths(config)
        self.assertIn("paths is missing required keys: runtime_dir", str(ctx.exception))

    def test_validate_paths_missing_multiple_keys(self):
        """Test validate_paths with multiple missing keys."""
        config = {"runtime_dir": ".router"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_paths(config)
        error_msg = str(ctx.exception)
        self.assertIn("paths is missing required keys:", error_msg)
        self.assertIn("active_config", error_msg)
        self.assertIn("state_file", error_msg)
        self.assertIn("log_file", error_msg)

    def test_validate_paths_extra_keys_allowed(self):
        """Test validate_paths allows extra keys."""
        config = self._valid_paths_config()
        config["extra_key"] = "extra_value"
        try:
            ConfigValidator.validate_paths(config)
        except ConfigError:
            self.fail("Extra keys should be allowed in paths config")


class TestValidateService(unittest.TestCase):
    """Test validate_service method."""

    def _valid_service_config(self):
        """Return a valid service configuration."""
        return {
            "command": {"args": ["/path/to/service", "--flag"]},
            "host": "127.0.0.1",
            "port": 4000,
        }

    def test_validate_service_valid(self):
        """Test validate_service with valid config."""
        config = self._valid_service_config()
        try:
            ConfigValidator.validate_service("test_service", config)
        except ConfigError:
            self.fail("Valid service config should not raise ConfigError")

    def test_validate_service_not_dict(self):
        """Test validate_service with non-dict config."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", "not_a_dict")
        self.assertIn("services.test_service must be a dict", str(ctx.exception))

    def test_validate_service_missing_command(self):
        """Test validate_service with missing command."""
        config = {"host": "127.0.0.1", "port": 4000}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", config)
        self.assertIn("services.test_service.command must be provided", str(ctx.exception))

    def test_validate_service_command_not_dict(self):
        """Test validate_service with command not being a dict."""
        config = {"command": "not_a_dict"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", config)
        self.assertIn("services.test_service.command must be provided", str(ctx.exception))

    def test_validate_service_missing_args(self):
        """Test validate_service with missing args."""
        config = {"command": {}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", config)
        self.assertIn("services.test_service.command.args must be a non-empty string list", str(ctx.exception))

    def test_validate_service_args_not_list(self):
        """Test validate_service with args not being a list."""
        config = {"command": {"args": "not_a_list"}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", config)
        self.assertIn("services.test_service.command.args must be a non-empty string list", str(ctx.exception))

    def test_validate_service_args_empty_list(self):
        """Test validate_service with empty args list."""
        config = {"command": {"args": []}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", config)
        self.assertIn("services.test_service.command.args must be a non-empty string list", str(ctx.exception))

    def test_validate_service_args_non_string_items(self):
        """Test validate_service with non-string items in args."""
        config = {"command": {"args": ["/path/to/service", 123, "--flag"]}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_service("test_service", config)
        self.assertIn("services.test_service.command.args must be a non-empty string list", str(ctx.exception))


class TestValidateServices(unittest.TestCase):
    """Test validate_services method."""

    def _valid_services_config(self):
        """Return a valid services configuration."""
        return {
            "litellm": {
                "command": {"args": ["/path/to/litellm"]},
                "host": "127.0.0.1",
                "port": 4000,
            },
            "cliproxyapi_plus": {
                "command": {"args": ["/path/to/cliproxyapi"]},
                "host": "127.0.0.1",
                "port": 9000,
            },
        }

    def test_validate_services_valid(self):
        """Test validate_services with valid config."""
        config = self._valid_services_config()
        try:
            ConfigValidator.validate_services(config)
        except ConfigError:
            self.fail("Valid services config should not raise ConfigError")

    def test_validate_services_missing_litellm(self):
        """Test validate_services with missing litellm."""
        config = {
            "cliproxyapi_plus": {
                "command": {"args": ["/path/to/cliproxyapi"]},
            }
        }
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_services(config)
        self.assertIn("services is missing required keys: litellm", str(ctx.exception))

    def test_validate_services_missing_cliproxyapi_plus(self):
        """Test validate_services with missing cliproxyapi_plus."""
        config = {
            "litellm": {
                "command": {"args": ["/path/to/litellm"]},
            }
        }
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_services(config)
        self.assertIn("services is missing required keys: cliproxyapi_plus", str(ctx.exception))

    def test_validate_services_invalid_service(self):
        """Test validate_services with invalid service config."""
        config = self._valid_services_config()
        config["litellm"]["command"]["args"] = []  # Invalid: empty args
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_services(config)
        self.assertIn("services.litellm.command.args must be a non-empty string list", str(ctx.exception))


class TestValidateLitellmBase(unittest.TestCase):
    """Test validate_litellm_base method."""

    def test_validate_litellm_base_valid(self):
        """Test validate_litellm_base with valid config."""
        config = {
            "model_list": [{"model_name": "test", "litellm_params": {"model": "gpt-4"}}],
            "router_settings": {},
            "litellm_settings": {},
        }
        try:
            ConfigValidator.validate_litellm_base(config)
        except ConfigError:
            self.fail("Valid litellm_base config should not raise ConfigError")

    def test_validate_litellm_base_minimal(self):
        """Test validate_litellm_base with minimal config."""
        config = {}
        try:
            ConfigValidator.validate_litellm_base(config)
        except ConfigError:
            self.fail("Minimal litellm_base config should not raise ConfigError")

    def test_validate_litellm_base_not_dict(self):
        """Test validate_litellm_base with non-dict config."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_litellm_base("not_a_dict")
        self.assertIn("litellm_base must be a dict", str(ctx.exception))

    def test_validate_litellm_base_list(self):
        """Test validate_litellm_base with list instead of dict."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_litellm_base([])
        self.assertIn("litellm_base must be a dict", str(ctx.exception))


class TestValidateProfiles(unittest.TestCase):
    """Test validate_profiles method."""

    def _valid_profiles_config(self):
        """Return a valid profiles configuration."""
        return {
            "reliability": {"litellm_settings": {"num_retries": 3}},
            "balanced": {"litellm_settings": {"num_retries": 2}},
            "cost": {"litellm_settings": {"num_retries": 1}},
        }

    def test_validate_profiles_valid(self):
        """Test validate_profiles with valid config."""
        config = self._valid_profiles_config()
        try:
            ConfigValidator.validate_profiles(config)
        except ConfigError:
            self.fail("Valid profiles config should not raise ConfigError")

    def test_validate_profiles_empty(self):
        """Test validate_profiles with empty dict."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_profiles({})
        self.assertIn("profiles must not be empty", str(ctx.exception))

    def test_validate_profiles_empty_name(self):
        """Test validate_profiles with empty profile name."""
        config = {"": {"litellm_settings": {}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_profiles(config)
        self.assertIn("profile names must be non-empty strings", str(ctx.exception))

    def test_validate_profiles_non_string_name(self):
        """Test validate_profiles with non-string profile name."""
        config = {123: {"litellm_settings": {}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_profiles(config)
        self.assertIn("profile names must be non-empty strings", str(ctx.exception))

    def test_validate_profiles_non_dict_value(self):
        """Test validate_profiles with non-dict profile value."""
        config = {"reliability": "not_a_dict"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_profiles(config)
        self.assertIn("profiles.reliability must be a dict", str(ctx.exception))


class TestValidateCredentials(unittest.TestCase):
    """Test validate_credentials method."""

    def _valid_credentials_config(self):
        """Return a valid credentials configuration."""
        return {
            "upstream": {
                "openai": {"file": ".router/secrets/openai.key"},
                "anthropic": {"file": ".router/secrets/anthropic.key"},
            }
        }

    def test_validate_credentials_valid(self):
        """Test validate_credentials with valid config."""
        config = self._valid_credentials_config()
        try:
            ConfigValidator.validate_credentials(config)
        except ConfigError:
            self.fail("Valid credentials config should not raise ConfigError")

    def test_validate_credentials_empty(self):
        """Test validate_credentials with empty config."""
        try:
            ConfigValidator.validate_credentials({})
        except ConfigError:
            self.fail("Empty credentials config should not raise ConfigError")

    def test_validate_credentials_unknown_key(self):
        """Test validate_credentials with unknown top-level key."""
        config = {"unknown_key": {}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials has unknown keys: unknown_key", str(ctx.exception))

    def test_validate_credentials_upstream_not_dict(self):
        """Test validate_credentials with upstream not being a dict."""
        config = {"upstream": "not_a_dict"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream must be a dict", str(ctx.exception))

    def test_validate_credentials_empty_upstream_name(self):
        """Test validate_credentials with empty upstream name."""
        config = {"upstream": {"": {"file": "path.key"}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream keys must be non-empty strings", str(ctx.exception))

    def test_validate_credentials_upstream_entry_not_dict(self):
        """Test validate_credentials with upstream entry not being a dict."""
        config = {"upstream": {"openai": "not_a_dict"}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream.openai must be a dict", str(ctx.exception))

    def test_validate_credentials_unknown_entry_key(self):
        """Test validate_credentials with unknown key in upstream entry."""
        config = {"upstream": {"openai": {"file": "path.key", "unknown": "value"}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream.openai has unknown keys: unknown", str(ctx.exception))

    def test_validate_credentials_missing_file(self):
        """Test validate_credentials with missing file key."""
        config = {"upstream": {"openai": {}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream.openai.file must be a non-empty string", str(ctx.exception))

    def test_validate_credentials_empty_file(self):
        """Test validate_credentials with empty file value."""
        config = {"upstream": {"openai": {"file": ""}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream.openai.file must be a non-empty string", str(ctx.exception))

    def test_validate_credentials_file_not_string(self):
        """Test validate_credentials with file not being a string."""
        config = {"upstream": {"openai": {"file": 123}}}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_credentials(config)
        self.assertIn("credentials.upstream.openai.file must be a non-empty string", str(ctx.exception))


class TestValidateOAuth(unittest.TestCase):
    """Test validate_oauth method (legacy)."""

    def test_validate_oauth_valid(self):
        """Test validate_oauth with valid config."""
        config = {
            "codex": {
                "auth_url_endpoint": "http://localhost:9000/auth-url",
                "status_endpoint": "http://localhost:9000/status",
            },
            "copilot": {
                "auth_url_endpoint": "http://localhost:9001/auth-url",
                "status_endpoint": "http://localhost:9001/status",
            },
        }
        try:
            ConfigValidator.validate_oauth(config)
        except ConfigError:
            self.fail("Valid oauth config should not raise ConfigError")

    def test_validate_oauth_empty(self):
        """Test validate_oauth with empty config."""
        try:
            ConfigValidator.validate_oauth({})
        except ConfigError:
            self.fail("Empty oauth config should not raise ConfigError")

    def test_validate_oauth_provider_not_dict(self):
        """Test validate_oauth with provider not being a dict."""
        config = {"codex": "not_a_dict"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_oauth(config)
        self.assertIn("oauth.codex must be a dict", str(ctx.exception))


class TestValidateAuthProviders(unittest.TestCase):
    """Test validate_auth_providers method."""

    def test_validate_auth_providers_valid(self):
        """Test validate_auth_providers with valid config."""
        config = {
            "codex": {
                "auth_url_endpoint": "http://localhost:9000/auth-url",
                "status_endpoint": "http://localhost:9000/status",
            },
            "copilot": {
                "auth_url_endpoint": "http://localhost:9001/auth-url",
                "status_endpoint": "http://localhost:9001/status",
            },
        }
        try:
            ConfigValidator.validate_auth_providers(config)
        except ConfigError:
            self.fail("Valid auth.providers config should not raise ConfigError")

    def test_validate_auth_providers_empty(self):
        """Test validate_auth_providers with empty config."""
        try:
            ConfigValidator.validate_auth_providers({})
        except ConfigError:
            self.fail("Empty auth.providers config should not raise ConfigError")

    def test_validate_auth_providers_provider_not_dict(self):
        """Test validate_auth_providers with provider not being a dict."""
        config = {"codex": "not_a_dict"}
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_auth_providers(config)
        self.assertIn("auth.providers.codex must be a dict", str(ctx.exception))


class TestValidateSecretFiles(unittest.TestCase):
    """Test validate_secret_files method."""

    def test_validate_secret_files_valid(self):
        """Test validate_secret_files with valid list."""
        secret_files = ["auth/codex.json", "auth/copilot.json", ".router/secrets/api.key"]
        try:
            ConfigValidator.validate_secret_files(secret_files)
        except ConfigError:
            self.fail("Valid secret_files should not raise ConfigError")

    def test_validate_secret_files_empty_list(self):
        """Test validate_secret_files with empty list."""
        try:
            ConfigValidator.validate_secret_files([])
        except ConfigError:
            self.fail("Empty secret_files list should not raise ConfigError")

    def test_validate_secret_files_not_list(self):
        """Test validate_secret_files with non-list value."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_secret_files("not_a_list")
        self.assertIn("secret_files must be a list of string paths", str(ctx.exception))

    def test_validate_secret_files_non_string_items(self):
        """Test validate_secret_files with non-string items."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_secret_files(["valid.json", 123, "another.key"])
        self.assertIn("secret_files must be a list of string paths", str(ctx.exception))

    def test_validate_secret_files_dict(self):
        """Test validate_secret_files with dict instead of list."""
        with self.assertRaises(ConfigError) as ctx:
            ConfigValidator.validate_secret_files({"file": "path.json"})
        self.assertIn("secret_files must be a list of string paths", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
