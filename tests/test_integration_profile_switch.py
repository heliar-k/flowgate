import io
import json
import tempfile
import unittest
from pathlib import Path

from flowgate.cli import run_cli
from tests.fixtures import ConfigFactory

import pytest


@pytest.mark.unit
class ProfileSwitchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.cfg_path = self.root / "flowgate.yaml"

        cfg = ConfigFactory.with_profiles(["reliability", "balanced"])
        # Add custom cost profile with specific cooldown_time for test
        cfg["profiles"]["cost"] = {
            "litellm_settings": {"num_retries": 1, "cooldown_time": 5}
        }
        cfg["paths"] = ConfigFactory.paths(
            runtime_dir=str(self.root / "runtime"),
            active_config=str(self.root / "runtime" / "litellm.active.yaml"),
            state_file=str(self.root / "runtime" / "state.json"),
            log_file=str(self.root / "logs" / "routerctl.log"),
        )
        cfg["litellm_base"]["litellm_settings"] = {"num_retries": 1, "cooldown_time": 10}
        cfg["litellm_base"]["router_settings"] = {"routing_strategy": "simple-shuffle"}
        cfg["secret_files"] = []

        self.cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    def test_switch_profile_updates_active_config(self):
        out = io.StringIO()
        code = run_cli(
            ["--config", str(self.cfg_path), "profile", "set", "reliability"],
            stdout=out,
        )
        self.assertEqual(code, 0)

        active = json.loads((self.root / "runtime" / "litellm.active.yaml").read_text())
        self.assertEqual(active["litellm_settings"]["num_retries"], 3)
        self.assertEqual(active["litellm_settings"]["cooldown_time"], 60)

        out = io.StringIO()
        code = run_cli(
            ["--config", str(self.cfg_path), "profile", "set", "cost"], stdout=out
        )
        self.assertEqual(code, 0)

        active = json.loads((self.root / "runtime" / "litellm.active.yaml").read_text())
        self.assertEqual(active["litellm_settings"]["num_retries"], 1)
        self.assertEqual(active["litellm_settings"]["cooldown_time"], 5)


if __name__ == "__main__":
    unittest.main()
