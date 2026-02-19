"""Tests for ConfigFactory."""

import unittest

from flowgate.config import load_router_config
from tests.fixtures import ConfigFactory


class TestConfigFactory(unittest.TestCase):
    """Test ConfigFactory methods produce valid configurations."""

    def test_minimal_config_is_valid(self):
        """Minimal config should have all required keys."""
        config = ConfigFactory.minimal()

        self.assertIn("paths", config)
        self.assertIn("services", config)
        self.assertIn("litellm_base", config)
        self.assertIn("profiles", config)

        # Services should have required keys
        self.assertIn("litellm", config["services"])
        self.assertIn("cliproxyapi_plus", config["services"])

        # Each service should have required fields
        for service_name in ["litellm", "cliproxyapi_plus"]:
            service = config["services"][service_name]
            self.assertIn("command", service)
            self.assertIn("host", service)
            self.assertIn("port", service)
            self.assertIn("readiness_path", service)

    def test_minimal_config_has_no_config_version(self):
        """Minimal config should not set config_version (relies on default)."""
        config = ConfigFactory.minimal()
        self.assertNotIn("config_version", config)

    def test_with_config_version_sets_version(self):
        """with_config_version should set explicit version."""
        config = ConfigFactory.with_config_version(2)
        self.assertEqual(config["config_version"], 2)

    def test_with_auth_creates_auth_providers(self):
        """with_auth should create auth.providers section."""
        config = ConfigFactory.with_auth(["codex", "copilot"])

        self.assertIn("auth", config)
        self.assertIn("providers", config["auth"])
        self.assertIn("codex", config["auth"]["providers"])
        self.assertIn("copilot", config["auth"]["providers"])

        # Check provider structure
        codex = config["auth"]["providers"]["codex"]
        self.assertIn("method", codex)
        self.assertIn("auth_url_endpoint", codex)
        self.assertIn("status_endpoint", codex)

    def test_with_auth_defaults_to_codex_copilot(self):
        """with_auth with no args should default to codex and copilot."""
        config = ConfigFactory.with_auth()
        self.assertIn("codex", config["auth"]["providers"])
        self.assertIn("copilot", config["auth"]["providers"])

    def test_with_oauth_creates_legacy_oauth_section(self):
        """with_oauth should create legacy oauth section for v1 compat."""
        config = ConfigFactory.with_oauth(["codex"])

        self.assertIn("oauth", config)
        self.assertIn("codex", config["oauth"])
        self.assertIn("auth_url_endpoint", config["oauth"]["codex"])
        self.assertIn("status_endpoint", config["oauth"]["codex"])

    def test_with_credentials_creates_upstream_section(self):
        """with_credentials should create credentials.upstream section."""
        config = ConfigFactory.with_credentials({
            "openai": "/path/to/openai.key",
            "anthropic": "/path/to/anthropic.key",
        })

        self.assertIn("credentials", config)
        self.assertIn("upstream", config["credentials"])
        self.assertIn("openai", config["credentials"]["upstream"])
        self.assertIn("anthropic", config["credentials"]["upstream"])

        # Check structure
        openai = config["credentials"]["upstream"]["openai"]
        self.assertEqual(openai["file"], "/path/to/openai.key")

    def test_with_profiles_creates_profiles(self):
        """with_profiles should create profile configurations."""
        config = ConfigFactory.with_profiles(["reliability", "balanced", "cost"])

        self.assertIn("profiles", config)
        self.assertIn("reliability", config["profiles"])
        self.assertIn("balanced", config["profiles"])
        self.assertIn("cost", config["profiles"])

        # Check profile has litellm_settings
        reliability = config["profiles"]["reliability"]
        self.assertIn("litellm_settings", reliability)
        self.assertEqual(reliability["litellm_settings"]["num_retries"], 3)

    def test_with_profiles_defaults_to_standard_profiles(self):
        """with_profiles with no args should create standard profiles."""
        config = ConfigFactory.with_profiles()
        self.assertIn("reliability", config["profiles"])
        self.assertIn("balanced", config["profiles"])
        self.assertIn("cost", config["profiles"])

    def test_with_secret_files_creates_list(self):
        """with_secret_files should create secret_files list."""
        config = ConfigFactory.with_secret_files(["auth/codex.json", "auth/copilot.json"])

        self.assertIn("secret_files", config)
        self.assertEqual(len(config["secret_files"]), 2)
        self.assertIn("auth/codex.json", config["secret_files"])

    def test_full_featured_has_all_sections(self):
        """full_featured should include all optional sections."""
        config = ConfigFactory.full_featured()

        self.assertIn("auth", config)
        self.assertIn("credentials", config)
        self.assertIn("profiles", config)
        self.assertIn("secret_files", config)

        # Verify content
        self.assertIn("codex", config["auth"]["providers"])
        self.assertIn("openai", config["credentials"]["upstream"])
        self.assertIn("reliability", config["profiles"])
        self.assertEqual(len(config["secret_files"]), 2)

    def test_service_factory_creates_valid_service(self):
        """service() should create valid service config."""
        service = ConfigFactory.service("test-service", 8080)

        self.assertIn("command", service)
        self.assertIn("host", service)
        self.assertIn("port", service)
        self.assertIn("readiness_path", service)
        self.assertEqual(service["port"], 8080)
        self.assertEqual(service["host"], "127.0.0.1")

    def test_service_factory_accepts_custom_args(self):
        """service() should accept custom command args."""
        service = ConfigFactory.service(
            "custom",
            9000,
            host="0.0.0.0",
            readiness_path="/ready",
            command_args=["echo", "test"],
        )

        self.assertEqual(service["host"], "0.0.0.0")
        self.assertEqual(service["readiness_path"], "/ready")
        self.assertEqual(service["command"]["args"], ["echo", "test"])

    def test_litellm_base_minimal_has_required_fields(self):
        """litellm_base_minimal should have all required fields."""
        base = ConfigFactory.litellm_base_minimal()

        self.assertIn("model_list", base)
        self.assertIn("router_settings", base)
        self.assertIn("litellm_settings", base)

        # Check model list structure
        self.assertEqual(len(base["model_list"]), 1)
        model = base["model_list"][0]
        self.assertIn("model_name", model)
        self.assertIn("litellm_params", model)

    def test_litellm_base_with_api_key_includes_key(self):
        """litellm_base_with_api_key should include api_key."""
        base = ConfigFactory.litellm_base_with_api_key("test-key-123")

        model = base["model_list"][0]
        self.assertEqual(model["litellm_params"]["api_key"], "test-key-123")

    def test_litellm_base_with_api_key_ref_includes_ref(self):
        """litellm_base_with_api_key_ref should include api_key_ref."""
        base = ConfigFactory.litellm_base_with_api_key_ref("my_credential")

        model = base["model_list"][0]
        self.assertEqual(model["litellm_params"]["api_key_ref"], "my_credential")
        self.assertNotIn("api_key", model["litellm_params"])

    def test_auth_provider_creates_valid_provider(self):
        """auth_provider() should create valid provider config."""
        provider = ConfigFactory.auth_provider("test-provider")

        self.assertIn("method", provider)
        self.assertIn("auth_url_endpoint", provider)
        self.assertIn("status_endpoint", provider)
        self.assertEqual(provider["method"], "oauth_poll")

    def test_auth_provider_accepts_custom_base_url(self):
        """auth_provider() should accept custom base URL."""
        provider = ConfigFactory.auth_provider(
            "custom",
            method="custom_method",
            base_url="https://example.com:8443",
        )

        self.assertEqual(provider["method"], "custom_method")
        self.assertIn("https://example.com:8443", provider["auth_url_endpoint"])
        self.assertIn("https://example.com:8443", provider["status_endpoint"])

    def test_profile_creates_valid_profile(self):
        """profile() should create valid profile config."""
        profile = ConfigFactory.profile("reliability")

        self.assertIn("litellm_settings", profile)
        self.assertEqual(profile["litellm_settings"]["num_retries"], 3)
        self.assertEqual(profile["litellm_settings"]["cooldown_time"], 60)

    def test_profile_accepts_custom_settings(self):
        """profile() should merge custom settings."""
        profile = ConfigFactory.profile(
            "custom",
            custom_settings={"request_timeout": 120},
        )

        self.assertIn("litellm_settings", profile)
        self.assertEqual(profile["litellm_settings"]["request_timeout"], 120)

    def test_paths_factory_creates_valid_paths(self):
        """paths() should create valid paths config."""
        paths = ConfigFactory.paths(runtime_dir="/custom/runtime")

        self.assertIn("runtime_dir", paths)
        self.assertIn("active_config", paths)
        self.assertIn("state_file", paths)
        self.assertIn("log_file", paths)
        self.assertEqual(paths["runtime_dir"], "/custom/runtime")

    def test_paths_factory_accepts_custom_paths(self):
        """paths() should accept custom paths."""
        paths = ConfigFactory.paths(
            runtime_dir="/custom",
            active_config="/custom/active.yaml",
            state_file="/custom/state.json",
            log_file="/custom/events.log",
        )

        self.assertEqual(paths["active_config"], "/custom/active.yaml")
        self.assertEqual(paths["state_file"], "/custom/state.json")
        self.assertEqual(paths["log_file"], "/custom/events.log")

    def test_configs_are_mutable(self):
        """Factory-created configs should be mutable for test customization."""
        config = ConfigFactory.minimal()

        # Should be able to modify
        config["custom_field"] = "custom_value"
        config["profiles"]["new_profile"] = {"litellm_settings": {"num_retries": 5}}

        self.assertEqual(config["custom_field"], "custom_value")
        self.assertIn("new_profile", config["profiles"])

    def test_configs_are_independent(self):
        """Multiple calls should return independent configs."""
        config1 = ConfigFactory.minimal()
        config2 = ConfigFactory.minimal()

        config1["custom"] = "value1"
        config2["custom"] = "value2"

        self.assertEqual(config1["custom"], "value1")
        self.assertEqual(config2["custom"], "value2")

    def test_combining_factory_methods(self):
        """Factory methods should be composable."""
        # Start with minimal, add auth
        config = ConfigFactory.minimal()
        config["auth"] = {"providers": {
            "codex": ConfigFactory.auth_provider("codex"),
        }}
        config["credentials"] = {"upstream": {
            "openai": {"file": "/path/to/key"},
        }}

        self.assertIn("auth", config)
        self.assertIn("credentials", config)
        self.assertIn("codex", config["auth"]["providers"])
        self.assertIn("openai", config["credentials"]["upstream"])


if __name__ == "__main__":
    unittest.main()
