import io
import json
import tempfile
import unittest
from pathlib import Path

from llm_router.cli import run_cli
from llm_router.constants import DEFAULT_SERVICE_HOST, DEFAULT_SERVICE_PORTS, DEFAULT_SERVICE_READINESS_PATHS


class ProfileSwitchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg_path = self.root / "routertool.yaml"
        cfg = {
            "paths": {
                "runtime_dir": str(self.root / "runtime"),
                "active_config": str(self.root / "runtime" / "litellm.active.yaml"),
                "state_file": str(self.root / "runtime" / "state.json"),
                "log_file": str(self.root / "logs" / "routerctl.log"),
            },
            "services": {
                "litellm": {
                    "host": DEFAULT_SERVICE_HOST,
                    "port": DEFAULT_SERVICE_PORTS["litellm"],
                    "readiness_path": DEFAULT_SERVICE_READINESS_PATHS["litellm"],
                    "command": {"args": ["python", "-c", "import time; time.sleep(60)"]},
                },
                "cliproxyapi_plus": {
                    "host": DEFAULT_SERVICE_HOST,
                    "port": DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
                    "readiness_path": DEFAULT_SERVICE_READINESS_PATHS["cliproxyapi_plus"],
                    "command": {"args": ["python", "-c", "import time; time.sleep(60)"]},
                },
            },
            "litellm_base": {
                "litellm_settings": {"num_retries": 1, "cooldown_time": 10},
                "router_settings": {"routing_strategy": "simple-shuffle"},
            },
            "profiles": {
                "reliability": {
                    "litellm_settings": {"num_retries": 3, "cooldown_time": 60},
                },
                "balanced": {
                    "litellm_settings": {"num_retries": 2, "cooldown_time": 30},
                },
                "cost": {
                    "litellm_settings": {"num_retries": 1, "cooldown_time": 5},
                },
            },
            "oauth": {},
            "secret_files": [],
        }
        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    def test_switch_profile_updates_active_config(self):
        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg_path), "profile", "set", "reliability"], stdout=out)
        self.assertEqual(code, 0)

        active = json.loads((self.root / "runtime" / "litellm.active.yaml").read_text())
        self.assertEqual(active["litellm_settings"]["num_retries"], 3)
        self.assertEqual(active["litellm_settings"]["cooldown_time"], 60)

        out = io.StringIO()
        code = run_cli(["--config", str(self.cfg_path), "profile", "set", "cost"], stdout=out)
        self.assertEqual(code, 0)

        active = json.loads((self.root / "runtime" / "litellm.active.yaml").read_text())
        self.assertEqual(active["litellm_settings"]["num_retries"], 1)
        self.assertEqual(active["litellm_settings"]["cooldown_time"], 5)


if __name__ == "__main__":
    unittest.main()
