import json
import tempfile
import unittest
from pathlib import Path

from flowgate.profile import activate_profile
from tests.fixtures import ConfigFactory


class ProfileActivationTests(unittest.TestCase):
    def _config(self, root: Path) -> dict:
        """Create test config using ConfigFactory."""
        config = ConfigFactory.minimal()
        config["paths"] = ConfigFactory.paths(
            runtime_dir=str(root / "runtime"),
            active_config=str(root / "runtime" / "litellm.active.yaml"),
            state_file=str(root / "runtime" / "state.json"),
            log_file=str(root / "logs" / "routerctl.log"),
        )
        config["profiles"] = {
            "balanced": {
                "litellm_settings": {"num_retries": 2},
                "router_settings": {"routing_strategy": "simple-shuffle"},
            }
        }
        return config

    def test_activate_profile_writes_active_config_and_state(self):
        root = Path(tempfile.mkdtemp())
        cfg = self._config(root)

        active_path, state_path = activate_profile(
            cfg, "balanced", now_iso="2026-02-16T00:00:00Z"
        )

        self.assertTrue(active_path.exists())
        self.assertTrue(state_path.exists())

        active_doc = json.loads(active_path.read_text())
        state_doc = json.loads(state_path.read_text())

        self.assertEqual(active_doc["litellm_settings"]["num_retries"], 2)
        self.assertEqual(state_doc["current_profile"], "balanced")

    def test_activate_profile_resolves_api_key_ref_to_api_key(self):
        root = Path(tempfile.mkdtemp())
        key_file = root / "secrets" / "coproxy.key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text("sk-coproxy\n", encoding="utf-8")

        cfg = self._config(root)
        cfg["credentials"] = {
            "upstream": {
                "coproxy_local": {"file": str(key_file)},
            }
        }
        cfg["litellm_base"]["model_list"] = [
            {
                "model_name": "router-default",
                "litellm_params": {
                    "model": "openai/router-default",
                    "api_key_ref": "coproxy_local",
                },
            }
        ]

        active_path, _ = activate_profile(cfg, "balanced")
        active_doc = json.loads(active_path.read_text(encoding="utf-8"))
        params = active_doc["model_list"][0]["litellm_params"]
        self.assertEqual(params["api_key"], "sk-coproxy")
        self.assertNotIn("api_key_ref", params)

    def test_activate_profile_rejects_unknown_api_key_ref(self):
        root = Path(tempfile.mkdtemp())
        cfg = self._config(root)
        cfg["credentials"] = {"upstream": {}}
        cfg["litellm_base"]["model_list"] = [
            {
                "model_name": "router-default",
                "litellm_params": {
                    "model": "openai/router-default",
                    "api_key_ref": "missing_ref",
                },
            }
        ]

        with self.assertRaises(ValueError):
            activate_profile(cfg, "balanced")


if __name__ == "__main__":
    unittest.main()
