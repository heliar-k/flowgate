import json
import tempfile
import unittest
from pathlib import Path

from flowgate.config import ConfigError, load_router_config, merge_dicts
from flowgate.constants import DEFAULT_SERVICE_PORTS
from tests.fixtures import ConfigFactory

import pytest


@pytest.mark.unit
class ConfigTests(unittest.TestCase):
    def _write_config(self, data: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        tmp.write(json.dumps(data))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)

    def _base_config(self) -> dict:
        """Create base config for tests using ConfigFactory."""
        config = ConfigFactory.with_profiles(["reliability", "balanced", "cost"])
        config["paths"] = ConfigFactory.paths(
            runtime_dir="runtime",
            active_config="runtime/litellm.active.yaml",
            state_file="runtime/state.json",
            log_file="logs/routerctl.log",
        )
        config["auth"] = {
            "providers": {
                "codex": {
                    "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                    "status_endpoint": "http://127.0.0.1:9000/status",
                },
                "copilot": {
                    "auth_url_endpoint": "http://127.0.0.1:9001/auth-url",
                    "status_endpoint": "http://127.0.0.1:9001/status",
                },
            }
        }
        config["secret_files"] = ["auth/codex.json", "auth/copilot.json"]
        return config

    def test_load_valid_config(self):
        path = self._write_config(self._base_config())
        cfg = load_router_config(path)

        self.assertIn("services", cfg)
        self.assertEqual(
            cfg["services"]["litellm"]["port"], DEFAULT_SERVICE_PORTS["litellm"]
        )
        self.assertIn("balanced", cfg["profiles"])

    def test_reject_unknown_top_level_key(self):
        data = self._base_config()
        data["unexpected"] = {"x": 1}
        path = self._write_config(data)

        with self.assertRaises(ConfigError):
            load_router_config(path)

    def test_defaults_config_version_to_2(self):
        path = self._write_config(self._base_config())
        cfg = load_router_config(path)
        self.assertEqual(cfg["config_version"], 2)

    def test_rejects_unsupported_config_version(self):
        data = self._base_config()
        data["config_version"] = 99
        path = self._write_config(data)

        with self.assertRaises(ConfigError):
            load_router_config(path)

    def test_load_auth_providers_new_schema(self):
        data = self._base_config()
        data["auth"] = {
            "providers": {
                "codex": {
                    "method": "oauth_poll",
                    "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                    "status_endpoint": "http://127.0.0.1:9000/status",
                }
            }
        }
        path = self._write_config(data)
        cfg = load_router_config(path)
        self.assertIn("auth", cfg)
        self.assertIn("codex", cfg["auth"]["providers"])

    def test_merge_dicts_deep(self):
        base = {
            "litellm_settings": {"num_retries": 1, "cooldown_time": 10},
            "router_settings": {"routing_strategy": "simple-shuffle"},
        }
        overlay = {
            "litellm_settings": {"num_retries": 3},
            "router_settings": {"enable_pre_call_checks": True},
        }

        merged = merge_dicts(base, overlay)

        self.assertEqual(merged["litellm_settings"]["num_retries"], 3)
        self.assertEqual(merged["litellm_settings"]["cooldown_time"], 10)
        self.assertEqual(
            merged["router_settings"]["routing_strategy"], "simple-shuffle"
        )
        self.assertTrue(merged["router_settings"]["enable_pre_call_checks"])

    def test_load_credentials_schema(self):
        data = self._base_config()
        data["credentials"] = {
            "upstream": {
                "coproxy_local": {"file": "/tmp/coproxy.key"},
            }
        }
        path = self._write_config(data)
        cfg = load_router_config(path)
        self.assertIn("credentials", cfg)
        self.assertEqual(
            cfg["credentials"]["upstream"]["coproxy_local"]["file"],
            "/tmp/coproxy.key",
        )

    def test_rejects_invalid_credentials_schema(self):
        data = self._base_config()
        data["credentials"] = {"upstream": {"coproxy_local": {"file": 123}}}
        path = self._write_config(data)

        with self.assertRaises(ConfigError):
            load_router_config(path)

    def test_rejects_config_version_1(self):
        """Test that config_version 1 is rejected."""
        data = self._base_config()
        data["config_version"] = 1
        path = self._write_config(data)

        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)

        self.assertIn("Unsupported config_version=1", str(ctx.exception))

    def test_rejects_legacy_oauth_key(self):
        """Test that the legacy 'oauth' top-level key is rejected."""
        data = self._base_config()
        data["oauth"] = {
            "codex": {
                "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                "status_endpoint": "http://127.0.0.1:9000/status",
            }
        }
        path = self._write_config(data)

        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)

        self.assertIn("Unknown top-level keys: oauth", str(ctx.exception))

    def test_rejects_legacy_secrets_key(self):
        """Test that the legacy 'secrets' top-level key is rejected."""
        data = self._base_config()
        data["secrets"] = data.pop("secret_files")
        path = self._write_config(data)

        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)

        self.assertIn("Unknown top-level keys: secrets", str(ctx.exception))

    def test_no_deprecation_warning_for_config_version_2(self):
        """Test that config_version 2 works without issues."""
        data = self._base_config()
        data["config_version"] = 2
        path = self._write_config(data)
        cfg = load_router_config(path)
        self.assertEqual(cfg["config_version"], 2)

    def test_no_deprecation_warning_when_version_defaults_to_2(self):
        """Test that defaulting to version 2 works without issues."""
        data = self._base_config()
        path = self._write_config(data)
        cfg = load_router_config(path)
        self.assertEqual(cfg["config_version"], 2)


if __name__ == "__main__":
    unittest.main()
