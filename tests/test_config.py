import json
import tempfile
import unittest
from pathlib import Path

from flowgate.config import ConfigError, load_router_config, merge_dicts
from flowgate.constants import (
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORTS,
    DEFAULT_SERVICE_READINESS_PATHS,
)


class ConfigTests(unittest.TestCase):
    def _write_config(self, data: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        tmp.write(json.dumps(data))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)

    def _base_config(self) -> dict:
        return {
            "paths": {
                "runtime_dir": "runtime",
                "active_config": "runtime/litellm.active.yaml",
                "state_file": "runtime/state.json",
                "log_file": "logs/routerctl.log",
            },
            "services": {
                "litellm": {
                    "host": DEFAULT_SERVICE_HOST,
                    "port": DEFAULT_SERVICE_PORTS["litellm"],
                    "readiness_path": DEFAULT_SERVICE_READINESS_PATHS["litellm"],
                    "command": {
                        "args": [
                            "python",
                            "-m",
                            "http.server",
                            str(DEFAULT_SERVICE_PORTS["litellm"]),
                        ]
                    },
                },
                "cliproxyapi_plus": {
                    "host": DEFAULT_SERVICE_HOST,
                    "port": DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
                    "readiness_path": DEFAULT_SERVICE_READINESS_PATHS[
                        "cliproxyapi_plus"
                    ],
                    "command": {
                        "args": [
                            "python",
                            "-m",
                            "http.server",
                            str(DEFAULT_SERVICE_PORTS["cliproxyapi_plus"]),
                        ]
                    },
                },
            },
            "litellm_base": {
                "model_list": [
                    {
                        "model_name": "router-default",
                        "litellm_params": {"model": "openai/gpt-4o"},
                    }
                ]
            },
            "profiles": {
                "reliability": {
                    "litellm_settings": {"num_retries": 3, "cooldown_time": 60}
                },
                "balanced": {
                    "litellm_settings": {"num_retries": 2, "cooldown_time": 30}
                },
                "cost": {"litellm_settings": {"num_retries": 1, "cooldown_time": 10}},
            },
            "oauth": {
                "codex": {
                    "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                    "status_endpoint": "http://127.0.0.1:9000/status",
                },
                "copilot": {
                    "auth_url_endpoint": "http://127.0.0.1:9001/auth-url",
                    "status_endpoint": "http://127.0.0.1:9001/status",
                },
            },
            "secret_files": ["auth/codex.json", "auth/copilot.json"],
        }

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


if __name__ == "__main__":
    unittest.main()
