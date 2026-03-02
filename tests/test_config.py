import json
import tempfile
import unittest
from pathlib import Path

import pytest

from flowgate.core.config import ConfigError, load_router_config, merge_dicts
from flowgate.constants import DEFAULT_SERVICE_HOST, DEFAULT_SERVICE_PORTS
from tests.fixtures import ConfigFactory


@pytest.mark.unit
class ConfigTests(unittest.TestCase):
    def _write_project_config(
        self, flowgate: dict, cliproxy: dict | None = None
    ) -> Path:
        root = Path(tempfile.mkdtemp())
        cfg_dir = root / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)

        cliproxy_path = cfg_dir / "cliproxyapi.yaml"
        cliproxy_data = (
            cliproxy if cliproxy is not None else ConfigFactory.cliproxyapi_config()
        )
        cliproxy_path.write_text(json.dumps(cliproxy_data), encoding="utf-8")

        flowgate_path = cfg_dir / "flowgate.yaml"
        flowgate_path.write_text(json.dumps(flowgate), encoding="utf-8")
        return flowgate_path

    def _base_config(self) -> dict:
        root = Path(tempfile.mkdtemp())
        runtime_dir = root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return ConfigFactory.minimal(
            runtime_dir=str(runtime_dir),
            log_file=str(runtime_dir / "events.log"),
            cliproxy_config_file="cliproxyapi.yaml",
        )

    def test_load_valid_config(self):
        data = self._base_config()
        path = self._write_project_config(data)
        cfg = load_router_config(path)

        self.assertEqual(cfg["config_version"], 3)
        self.assertEqual(
            cfg["services"]["cliproxyapi_plus"]["port"],
            DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
        )
        self.assertEqual(
            cfg["services"]["cliproxyapi_plus"]["host"], DEFAULT_SERVICE_HOST
        )

    def test_reject_unknown_top_level_key(self):
        data = self._base_config()
        data["unexpected"] = {"x": 1}
        path = self._write_project_config(data)

        with self.assertRaises(ConfigError):
            load_router_config(path)

    def test_defaults_config_version_to_3(self):
        data = self._base_config()
        del data["config_version"]
        path = self._write_project_config(data)
        cfg = load_router_config(path)
        self.assertEqual(cfg["config_version"], 3)

    def test_rejects_unsupported_config_version(self):
        data = self._base_config()
        data["config_version"] = 99
        path = self._write_project_config(data)

        with self.assertRaises(ConfigError):
            load_router_config(path)

    def test_load_auth_providers(self):
        data = self._base_config()
        data["auth"] = {
            "providers": {
                "codex": ConfigFactory.auth_provider("codex"),
            }
        }
        path = self._write_project_config(data)
        cfg = load_router_config(path)
        self.assertIn("codex", cfg["auth"]["providers"])

    def test_merge_dicts_deep(self):
        base = {
            "settings": {"retries": 1, "cooldown": 10},
            "router": {"strategy": "simple-shuffle"},
        }
        overlay = {
            "settings": {"retries": 3},
            "router": {"pre_call_checks": True},
        }

        merged = merge_dicts(base, overlay)

        self.assertEqual(merged["settings"]["retries"], 3)
        self.assertEqual(merged["settings"]["cooldown"], 10)
        self.assertEqual(merged["router"]["strategy"], "simple-shuffle")
        self.assertTrue(merged["router"]["pre_call_checks"])


if __name__ == "__main__":
    unittest.main()
