import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from flowgate.config import ConfigError, load_router_config, merge_dicts
from flowgate.constants import DEFAULT_SERVICE_PORTS
from tests.fixtures import ConfigFactory


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
        config["oauth"] = {
            "codex": {
                "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                "status_endpoint": "http://127.0.0.1:9000/status",
            },
            "copilot": {
                "auth_url_endpoint": "http://127.0.0.1:9001/auth-url",
                "status_endpoint": "http://127.0.0.1:9001/status",
            },
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

    def test_migrates_legacy_secrets_key(self):
        data = self._base_config()
        data["secrets"] = data.pop("secret_files")
        path = self._write_config(data)
        cfg = load_router_config(path)
        self.assertEqual(cfg["secret_files"], ["auth/codex.json", "auth/copilot.json"])

    def test_migrates_legacy_cliproxyapi_service_name(self):
        data = self._base_config()
        data["services"]["cliproxyapi"] = data["services"].pop("cliproxyapi_plus")
        path = self._write_config(data)
        cfg = load_router_config(path)
        self.assertIn("cliproxyapi_plus", cfg["services"])

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
        data.pop("oauth", None)
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

    def test_deprecation_warning_for_config_version_1(self):
        """Test that config_version 1 triggers deprecation warning."""
        data = self._base_config()
        data["config_version"] = 1
        path = self._write_config(data)

        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            cfg = load_router_config(path)
            warning_output = sys.stderr.getvalue()

            # Verify config still loads correctly
            self.assertEqual(cfg["config_version"], 1)

            # Verify deprecation warning is present
            self.assertIn("WARNING: config_version 1 is deprecated", warning_output)
            self.assertIn("will be removed in v0.3.0", warning_output)
            self.assertIn("flowgate config migrate --to-version 2", warning_output)
        finally:
            sys.stderr = old_stderr

    def test_deprecation_warning_includes_legacy_fields(self):
        """Test that deprecation warning lists detected legacy fields."""
        data = self._base_config()
        data["config_version"] = 1
        # Use legacy field names
        data["secrets"] = data.pop("secret_files")
        data["services"]["cliproxyapi"] = data["services"].pop("cliproxyapi_plus")
        path = self._write_config(data)

        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            cfg = load_router_config(path)
            warning_output = sys.stderr.getvalue()

            # Verify legacy fields are mentioned
            self.assertIn("Legacy field mappings detected:", warning_output)
            self.assertIn("'secrets' → use 'secret_files' instead", warning_output)
            self.assertIn("'cliproxyapi' → use 'cliproxyapi_plus' instead", warning_output)
            self.assertIn("'oauth' → use 'auth.providers' instead", warning_output)

            # Verify config still works
            self.assertIn("cliproxyapi_plus", cfg["services"])
            self.assertEqual(cfg["secret_files"], ["auth/codex.json", "auth/copilot.json"])
        finally:
            sys.stderr = old_stderr

    def test_no_deprecation_warning_for_config_version_2(self):
        """Test that config_version 2 does not trigger deprecation warning."""
        data = self._base_config()
        data["config_version"] = 2
        path = self._write_config(data)

        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            cfg = load_router_config(path)
            warning_output = sys.stderr.getvalue()

            # Verify no deprecation warning
            self.assertEqual(warning_output, "")
            self.assertEqual(cfg["config_version"], 2)
        finally:
            sys.stderr = old_stderr

    def test_no_deprecation_warning_when_version_defaults_to_2(self):
        """Test that defaulting to version 2 does not trigger warning."""
        data = self._base_config()
        # Don't specify config_version, should default to 2
        path = self._write_config(data)

        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            cfg = load_router_config(path)
            warning_output = sys.stderr.getvalue()

            # Verify no deprecation warning
            self.assertEqual(warning_output, "")
            self.assertEqual(cfg["config_version"], 2)
        finally:
            sys.stderr = old_stderr


if __name__ == "__main__":
    unittest.main()
