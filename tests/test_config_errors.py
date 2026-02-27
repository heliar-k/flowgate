"""Error path tests for configuration module (v3-only)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest

from flowgate.config import ConfigError, load_router_config
from tests.fixtures import ConfigFactory


@pytest.mark.unit
class TestConfigErrorHandling(unittest.TestCase):
    def _write_project(
        self,
        *,
        flowgate: dict,
        cliproxy: dict | None = None,
        write_cliproxy: bool = True,
    ) -> Path:
        root = Path(tempfile.mkdtemp())
        cfg_dir = root / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)

        if write_cliproxy:
            cliproxy_path = cfg_dir / "cliproxyapi.yaml"
            cliproxy_path.write_text(
                json.dumps(cliproxy if cliproxy is not None else ConfigFactory.cliproxyapi_config()),
                encoding="utf-8",
            )

        flowgate_path = cfg_dir / "flowgate.yaml"
        flowgate_path.write_text(json.dumps(flowgate), encoding="utf-8")
        return flowgate_path

    def _minimal_valid_flowgate(self) -> dict:
        root = Path(tempfile.mkdtemp())
        runtime_dir = root / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        return ConfigFactory.minimal(
            runtime_dir=str(runtime_dir),
            log_file=str(runtime_dir / "events.log"),
            cliproxy_config_file="cliproxyapi.yaml",
        )

    def test_missing_required_key_paths(self):
        cfg = self._minimal_valid_flowgate()
        del cfg["paths"]
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Missing required top-level keys: paths", str(ctx.exception))

    def test_missing_required_key_cliproxy_section(self):
        cfg = self._minimal_valid_flowgate()
        del cfg["cliproxyapi_plus"]
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Missing required top-level keys: cliproxyapi_plus", str(ctx.exception))

    def test_unknown_top_level_key(self):
        cfg = self._minimal_valid_flowgate()
        cfg["unknown_field"] = "should-not-exist"
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Unknown top-level keys", str(ctx.exception))
        self.assertIn("unknown_field", str(ctx.exception))

    def test_invalid_config_version_type(self):
        cfg = self._minimal_valid_flowgate()
        cfg["config_version"] = "3"
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("config_version must be an integer", str(ctx.exception))

    def test_unsupported_config_version(self):
        cfg = self._minimal_valid_flowgate()
        cfg["config_version"] = 999
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Unsupported config_version", str(ctx.exception))

    def test_top_level_not_mapping(self):
        root = Path(tempfile.mkdtemp())
        cfg_dir = root / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        path = cfg_dir / "flowgate.yaml"
        path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("Top-level config must be a mapping/object", str(ctx.exception))

    def test_paths_not_mapping(self):
        cfg = self._minimal_valid_flowgate()
        cfg["paths"] = "invalid"
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("paths must be a mapping/object", str(ctx.exception))

    def test_missing_required_paths_keys(self):
        cfg = self._minimal_valid_flowgate()
        del cfg["paths"]["runtime_dir"]
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("paths is missing required keys: runtime_dir", str(ctx.exception))

    def test_cliproxy_section_not_mapping(self):
        cfg = self._minimal_valid_flowgate()
        cfg["cliproxyapi_plus"] = "invalid"
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("cliproxyapi_plus must be a mapping/object", str(ctx.exception))

    def test_missing_cliproxy_config_file_field(self):
        cfg = self._minimal_valid_flowgate()
        cfg["cliproxyapi_plus"] = {}
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("cliproxyapi_plus.config_file must be a non-empty string", str(ctx.exception))

    def test_cliproxy_config_port_must_be_int(self):
        cfg = self._minimal_valid_flowgate()
        cliproxy = ConfigFactory.cliproxyapi_config()
        cliproxy["port"] = "8317"
        path = self._write_project(flowgate=cfg, cliproxy=cliproxy)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("CLIProxyAPIPlus config 'port' must be an integer", str(ctx.exception))

    def test_auth_provider_must_be_mapping(self):
        cfg = self._minimal_valid_flowgate()
        cfg["auth"] = {"providers": {"codex": "not-a-dict"}}
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("auth.providers.codex must be a dict", str(ctx.exception))

    def test_auth_provider_endpoints_must_be_non_empty(self):
        cfg = self._minimal_valid_flowgate()
        cfg["auth"] = {"providers": {"codex": {"auth_url_endpoint": "", "status_endpoint": "x"}}}
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("auth.providers.codex.auth_url_endpoint must be a non-empty string", str(ctx.exception))

    def test_secret_files_must_be_list(self):
        cfg = self._minimal_valid_flowgate()
        cfg["secret_files"] = "not-a-list"
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("secret_files must be a list of string paths", str(ctx.exception))

    def test_integration_unknown_key_rejected(self):
        cfg = self._minimal_valid_flowgate()
        cfg["integration"] = {"unknown": "x"}
        path = self._write_project(flowgate=cfg)
        with self.assertRaises(ConfigError) as ctx:
            load_router_config(path)
        self.assertIn("integration has unknown keys", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

