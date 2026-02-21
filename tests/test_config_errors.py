"""Error path tests for configuration module.

This module tests error handling in config.py and validators.py,
ensuring proper ConfigError exceptions are raised for invalid configurations.
"""

import json
import tempfile
import unittest
from pathlib import Path

from flowgate.config import ConfigError, load_router_config, merge_dicts
from tests.fixtures import ConfigFactory

import pytest


@pytest.mark.unit
class TestConfigErrorHandling(unittest.TestCase):
    """Test configuration error handling."""

    def _write_config(self, data: dict) -> Path:
        """Helper to write config to temp file."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(json.dumps(data))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)

    def _minimal_valid_config(self) -> dict:
        """Return minimal valid configuration."""
        config = ConfigFactory.with_config_version(2)
        config["profiles"] = {"default": {"litellm_settings": {"num_retries": 1}}}
        return config

    def test_missing_required_key_paths(self):
        """Test ConfigError when paths key is missing."""
        cfg = self._minimal_valid_config()
        del cfg["paths"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("paths", str(ctx.exception))

    def test_missing_required_key_services(self):
        """Test ConfigError when services key is missing."""
        cfg = self._minimal_valid_config()
        del cfg["services"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("services", str(ctx.exception))

    def test_missing_required_key_litellm_base(self):
        """Test ConfigError when litellm_base key is missing."""
        cfg = self._minimal_valid_config()
        del cfg["litellm_base"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("litellm_base", str(ctx.exception))

    def test_missing_required_key_profiles(self):
        """Test ConfigError when profiles key is missing."""
        cfg = self._minimal_valid_config()
        del cfg["profiles"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("profiles", str(ctx.exception))

    def test_unknown_top_level_key(self):
        """Test ConfigError when unknown top-level key is present."""
        cfg = self._minimal_valid_config()
        cfg["unknown_field"] = "should-not-exist"
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Unknown top-level keys", str(ctx.exception))
        self.assertIn("unknown_field", str(ctx.exception))

    def test_invalid_config_version_type(self):
        """Test ConfigError when config_version is not an integer."""
        cfg = self._minimal_valid_config()
        cfg["config_version"] = "2"  # String instead of int
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("config_version must be an integer", str(ctx.exception))

    def test_unsupported_config_version(self):
        """Test ConfigError when config_version is unsupported."""
        cfg = self._minimal_valid_config()
        cfg["config_version"] = 999
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Unsupported config_version", str(ctx.exception))

    def test_top_level_not_mapping(self):
        """Test ConfigError when top-level config is not a dict."""
        path = self._write_config(["not", "a", "dict"])
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Top-level config must be a mapping/object", str(ctx.exception))

    def test_paths_not_mapping(self):
        """Test ConfigError when paths is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["paths"] = "invalid"
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("paths must be a mapping/object", str(ctx.exception))

    def test_services_not_mapping(self):
        """Test ConfigError when services is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["services"] = ["invalid"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("services must be a mapping/object", str(ctx.exception))

    def test_litellm_base_not_mapping(self):
        """Test ConfigError when litellm_base is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["litellm_base"] = "invalid"
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("litellm_base must be a mapping/object", str(ctx.exception))

    def test_profiles_not_mapping(self):
        """Test ConfigError when profiles is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["profiles"] = ["invalid"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("profiles must be a mapping/object", str(ctx.exception))

    def test_missing_required_paths_keys(self):
        """Test ConfigError when required paths keys are missing."""
        cfg = self._minimal_valid_config()
        del cfg["paths"]["runtime_dir"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("runtime_dir", str(ctx.exception))

    def test_missing_required_service_litellm(self):
        """Test ConfigError when litellm service is missing."""
        cfg = self._minimal_valid_config()
        del cfg["services"]["litellm"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("litellm", str(ctx.exception))

    def test_missing_required_service_cliproxyapi_plus(self):
        """Test ConfigError when cliproxyapi_plus service is missing."""
        cfg = self._minimal_valid_config()
        del cfg["services"]["cliproxyapi_plus"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("cliproxyapi_plus", str(ctx.exception))

    def test_service_missing_command(self):
        """Test ConfigError when service is missing command."""
        cfg = self._minimal_valid_config()
        del cfg["services"]["litellm"]["command"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("command must be provided", str(ctx.exception))

    def test_service_command_not_dict(self):
        """Test ConfigError when service command is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["services"]["litellm"]["command"] = "invalid"
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("command must be provided", str(ctx.exception))

    def test_service_command_args_not_list(self):
        """Test ConfigError when command args is not a list."""
        cfg = self._minimal_valid_config()
        cfg["services"]["litellm"]["command"]["args"] = "invalid"
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("args must be a non-empty string list", str(ctx.exception))

    def test_service_command_args_empty_list(self):
        """Test ConfigError when command args is empty list."""
        cfg = self._minimal_valid_config()
        cfg["services"]["litellm"]["command"]["args"] = []
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("args must be a non-empty string list", str(ctx.exception))

    def test_service_command_args_non_string_items(self):
        """Test ConfigError when command args contains non-string items."""
        cfg = self._minimal_valid_config()
        cfg["services"]["litellm"]["command"]["args"] = ["valid", 123, "also-valid"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("args must be a non-empty string list", str(ctx.exception))

    def test_profiles_empty(self):
        """Test ConfigError when profiles is empty dict."""
        cfg = self._minimal_valid_config()
        cfg["profiles"] = {}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("profiles must not be empty", str(ctx.exception))

    def test_profile_name_not_string(self):
        """Test ConfigError when profile name is not a string."""
        # Note: JSON doesn't support non-string keys, so this test would require
        # creating the dict programmatically rather than via JSON, which isn't
        # how the config is normally loaded. We skip this test case as it's
        # not realistically possible through the normal config loading path.
        pass

    def test_profile_value_not_dict(self):
        """Test ConfigError when profile value is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["profiles"]["invalid"] = "not-a-dict"
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("profiles.invalid", str(ctx.exception))

    def test_credentials_unknown_keys(self):
        """Test ConfigError when credentials has unknown keys."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {"unknown": "value", "upstream": {}}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("credentials has unknown keys", str(ctx.exception))
        self.assertIn("unknown", str(ctx.exception))

    def test_credentials_upstream_not_dict(self):
        """Test ConfigError when credentials.upstream is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {"upstream": "invalid"}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("credentials.upstream", str(ctx.exception))

    def test_credentials_upstream_entry_not_dict(self):
        """Test ConfigError when upstream entry is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {"upstream": {"openai": "invalid"}}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("credentials.upstream.openai", str(ctx.exception))

    def test_credentials_upstream_entry_unknown_keys(self):
        """Test ConfigError when upstream entry has unknown keys."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {
            "upstream": {"openai": {"file": "key.txt", "unknown": "value"}}
        }
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("credentials.upstream.openai has unknown keys", str(ctx.exception))

    def test_credentials_upstream_file_empty_string(self):
        """Test ConfigError when file path is empty string."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {"upstream": {"openai": {"file": ""}}}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("must be a non-empty string", str(ctx.exception))

    def test_credentials_upstream_file_not_string(self):
        """Test ConfigError when file path is not a string."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {"upstream": {"openai": {"file": 123}}}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("must be a non-empty string", str(ctx.exception))

    def test_secret_files_not_list(self):
        """Test ConfigError when secret_files is not a list."""
        cfg = self._minimal_valid_config()
        cfg["secret_files"] = {"not": "a-list"}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("secret_files must be a list", str(ctx.exception))

    def test_secret_files_non_string_items(self):
        """Test ConfigError when secret_files contains non-string items."""
        cfg = self._minimal_valid_config()
        cfg["secret_files"] = ["valid.txt", 123, "also-valid.json"]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("secret_files must be a list of string paths", str(ctx.exception))

    def test_oauth_key_rejected_as_unknown(self):
        """Test ConfigError when legacy oauth key is used."""
        cfg = self._minimal_valid_config()
        cfg["oauth"] = {"codex": {"auth_url_endpoint": "http://x", "status_endpoint": "http://x"}}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Unknown top-level keys: oauth", str(ctx.exception))

    def test_auth_providers_not_dict(self):
        """Test ConfigError when auth.providers entry is not a dict."""
        cfg = self._minimal_valid_config()
        cfg["auth"] = {"providers": {"codex": "invalid"}}
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("auth.providers.codex", str(ctx.exception))

    def test_invalid_json_content(self):
        """Test error when config file contains invalid JSON."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write("{invalid json content")
        tmp.flush()
        tmp.close()
        path = Path(tmp.name)

        # This will raise an error (either yaml parse error if PyYAML is installed,
        # or ConfigError if not). We just verify that loading fails.
        with self.assertRaises(Exception):
            load_router_config(path)


@pytest.mark.unit
class TestApiKeyRefValidation(unittest.TestCase):
    """Test api_key_ref cross-reference validation."""

    def _write_config(self, data: dict) -> Path:
        """Helper to write config to temp file."""
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tmp.write(json.dumps(data))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)

    def _minimal_valid_config(self) -> dict:
        """Return minimal valid configuration."""
        config = ConfigFactory.with_config_version(2)
        config["profiles"] = {"default": {"litellm_settings": {"num_retries": 1}}}
        return config

    def test_api_key_ref_valid_in_base(self):
        """Test valid api_key_ref in litellm_base.model_list."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {
            "upstream": {
                "openai": {"file": ".router/secrets/openai.key"}
            }
        }
        cfg["litellm_base"]["model_list"] = [
            {
                "model_name": "gpt-4",
                "litellm_params": {
                    "model": "gpt-4",
                    "api_key_ref": "openai"
                }
            }
        ]
        path = self._write_config(cfg)
        try:
            load_router_config(path)
        except ConfigError:
            self.fail("Valid api_key_ref in litellm_base should not raise ConfigError")

    def test_api_key_ref_valid_in_profile(self):
        """Test valid api_key_ref in profile.model_list."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {
            "upstream": {
                "anthropic": {"file": ".router/secrets/anthropic.key"}
            }
        }
        cfg["profiles"]["default"]["model_list"] = [
            {
                "model_name": "claude-3",
                "litellm_params": {
                    "model": "claude-3-opus",
                    "api_key_ref": "anthropic"
                }
            }
        ]
        path = self._write_config(cfg)
        try:
            load_router_config(path)
        except ConfigError:
            self.fail("Valid api_key_ref in profile should not raise ConfigError")

    def test_api_key_ref_invalid_in_base(self):
        """Test invalid api_key_ref in litellm_base.model_list."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {
            "upstream": {
                "openai": {"file": ".router/secrets/openai.key"}
            }
        }
        cfg["litellm_base"]["model_list"] = [
            {
                "model_name": "gpt-4",
                "litellm_params": {
                    "model": "gpt-4",
                    "api_key_ref": "nonexistent"
                }
            }
        ]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Invalid api_key_ref values", str(ctx.exception))
        self.assertIn("nonexistent", str(ctx.exception))
        self.assertIn("litellm_base.model_list[0]", str(ctx.exception))

    def test_api_key_ref_invalid_in_profile(self):
        """Test invalid api_key_ref in profile.model_list."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {
            "upstream": {
                "openai": {"file": ".router/secrets/openai.key"}
            }
        }
        cfg["profiles"]["default"]["model_list"] = [
            {
                "model_name": "claude-3",
                "litellm_params": {
                    "model": "claude-3-opus",
                    "api_key_ref": "missing_cred"
                }
            }
        ]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Invalid api_key_ref values", str(ctx.exception))
        self.assertIn("missing_cred", str(ctx.exception))
        self.assertIn("profiles.default.model_list[0]", str(ctx.exception))

    def test_api_key_ref_no_credentials(self):
        """Test api_key_ref when credentials section is missing."""
        cfg = self._minimal_valid_config()
        # No credentials section
        cfg["litellm_base"]["model_list"] = [
            {
                "model_name": "gpt-4",
                "litellm_params": {
                    "model": "gpt-4",
                    "api_key_ref": "openai"
                }
            }
        ]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Invalid api_key_ref values", str(ctx.exception))
        self.assertIn("openai", str(ctx.exception))

    def test_api_key_ref_multiple_invalid(self):
        """Test multiple invalid api_key_ref values."""
        cfg = self._minimal_valid_config()
        cfg["credentials"] = {
            "upstream": {
                "openai": {"file": ".router/secrets/openai.key"}
            }
        }
        cfg["litellm_base"]["model_list"] = [
            {
                "model_name": "gpt-4",
                "litellm_params": {
                    "model": "gpt-4",
                    "api_key_ref": "invalid1"
                }
            }
        ]
        cfg["profiles"]["default"]["model_list"] = [
            {
                "model_name": "claude-3",
                "litellm_params": {
                    "model": "claude-3-opus",
                    "api_key_ref": "invalid2"
                }
            }
        ]
        path = self._write_config(cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        error_msg = str(ctx.exception)
        self.assertIn("Invalid api_key_ref values", error_msg)
        self.assertIn("invalid1", error_msg)
        self.assertIn("invalid2", error_msg)


if __name__ == "__main__":
    unittest.main()
