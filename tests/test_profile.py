import json
import tempfile
import unittest
from pathlib import Path

from llm_router.profile import activate_profile


class ProfileActivationTests(unittest.TestCase):
    def _config(self, root: Path) -> dict:
        return {
            "paths": {
                "runtime_dir": str(root / "runtime"),
                "active_config": str(root / "runtime" / "litellm.active.yaml"),
                "state_file": str(root / "runtime" / "state.json"),
                "log_file": str(root / "logs" / "routerctl.log"),
            },
            "litellm_base": {
                "model_list": [{"model_name": "router-default", "litellm_params": {"model": "openai/gpt-4o"}}],
                "litellm_settings": {"num_retries": 1},
            },
            "profiles": {
                "balanced": {
                    "litellm_settings": {"num_retries": 2},
                    "router_settings": {"routing_strategy": "simple-shuffle"},
                }
            },
        }

    def test_activate_profile_writes_active_config_and_state(self):
        root = Path(tempfile.mkdtemp())
        cfg = self._config(root)

        active_path, state_path = activate_profile(cfg, "balanced", now_iso="2026-02-16T00:00:00Z")

        self.assertTrue(active_path.exists())
        self.assertTrue(state_path.exists())

        active_doc = json.loads(active_path.read_text())
        state_doc = json.loads(state_path.read_text())

        self.assertEqual(active_doc["litellm_settings"]["num_retries"], 2)
        self.assertEqual(state_doc["current_profile"], "balanced")


if __name__ == "__main__":
    unittest.main()
