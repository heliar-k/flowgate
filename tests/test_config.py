import json
import tempfile
import unittest
from pathlib import Path

from llm_router.config import ConfigError, load_router_config, merge_dicts


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
                    "host": "127.0.0.1",
                    "port": 4000,
                    "health_path": "/healthz",
                    "command": {"args": ["python", "-m", "http.server", "4000"]},
                },
                "cliproxyapi_plus": {
                    "host": "127.0.0.1",
                    "port": 8317,
                    "health_path": "/healthz",
                    "command": {"args": ["python", "-m", "http.server", "8317"]},
                },
            },
            "litellm_base": {
                "model_list": [{"model_name": "router-default", "litellm_params": {"model": "openai/gpt-4o"}}]
            },
            "profiles": {
                "reliability": {"litellm_settings": {"num_retries": 3, "cooldown_time": 60}},
                "balanced": {"litellm_settings": {"num_retries": 2, "cooldown_time": 30}},
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
        self.assertEqual(cfg["services"]["litellm"]["port"], 4000)
        self.assertIn("balanced", cfg["profiles"])

    def test_reject_unknown_top_level_key(self):
        data = self._base_config()
        data["unexpected"] = {"x": 1}
        path = self._write_config(data)

        with self.assertRaises(ConfigError):
            load_router_config(path)

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
        self.assertEqual(merged["router_settings"]["routing_strategy"], "simple-shuffle")
        self.assertTrue(merged["router_settings"]["enable_pre_call_checks"])


if __name__ == "__main__":
    unittest.main()
