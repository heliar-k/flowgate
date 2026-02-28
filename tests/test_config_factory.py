"""Tests for ConfigFactory (v3-only)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from flowgate.config import load_router_config
from flowgate.constants import (
    DEFAULT_READINESS_PATH,
    DEFAULT_SERVICE_HOST,
    DEFAULT_SERVICE_PORTS,
)
from tests.fixtures import ConfigFactory


@pytest.mark.unit
class TestConfigFactory(unittest.TestCase):
    """Test ConfigFactory methods produce valid v3 configurations."""

    def test_minimal_config_is_valid_v3_shape(self):
        config = ConfigFactory.minimal()

        self.assertEqual(config["config_version"], 3)
        self.assertIn("paths", config)
        self.assertIn("cliproxyapi_plus", config)

        self.assertIn("runtime_dir", config["paths"])
        self.assertIn("log_file", config["paths"])
        self.assertEqual(config["cliproxyapi_plus"]["config_file"], "cliproxyapi.yaml")

    def test_paths_factory_creates_valid_paths(self):
        paths = ConfigFactory.paths(runtime_dir="/custom/runtime")

        self.assertIn("runtime_dir", paths)
        self.assertIn("log_file", paths)
        self.assertEqual(paths["runtime_dir"], "/custom/runtime")
        self.assertEqual(paths["log_file"], "/custom/runtime/events.log")

    def test_cliproxyapi_config_defaults_match_constants(self):
        cfg = ConfigFactory.cliproxyapi_config()
        self.assertEqual(cfg["host"], DEFAULT_SERVICE_HOST)
        self.assertEqual(cfg["port"], DEFAULT_SERVICE_PORTS["cliproxyapi_plus"])

    def test_write_minimal_v3_writes_pair_and_loads(self):
        root = Path(tempfile.mkdtemp())
        flowgate_path = ConfigFactory.write_minimal_v3(root)

        loaded = load_router_config(flowgate_path)
        self.assertEqual(loaded["config_version"], 3)
        self.assertEqual(
            loaded["services"]["cliproxyapi_plus"]["port"],
            DEFAULT_SERVICE_PORTS["cliproxyapi_plus"],
        )
        self.assertEqual(
            loaded["services"]["cliproxyapi_plus"]["readiness_path"],
            DEFAULT_READINESS_PATH,
        )

        cliproxy_cfg = Path(loaded["cliproxyapi_plus"]["config_file"])
        self.assertTrue(cliproxy_cfg.exists())
        self.assertEqual(
            cliproxy_cfg,
            (root / "config" / "cliproxyapi.yaml").resolve(),
        )

    def test_auth_provider_creates_management_endpoints(self):
        provider = ConfigFactory.auth_provider("codex")
        self.assertEqual(provider["method"], "oauth_poll")
        self.assertIn(
            "/v0/management/oauth/codex/auth-url", provider["auth_url_endpoint"]
        )
        self.assertIn("/v0/management/oauth/codex/status", provider["status_endpoint"])

    def test_with_auth_creates_auth_providers(self):
        config = ConfigFactory.with_auth(["codex", "copilot"])
        providers = config["auth"]["providers"]

        self.assertIn("codex", providers)
        self.assertIn("copilot", providers)
        self.assertIn("auth_url_endpoint", providers["codex"])
        self.assertIn("status_endpoint", providers["codex"])

    def test_with_secret_files_creates_list(self):
        config = ConfigFactory.with_secret_files(
            ["auth/codex.json", "auth/copilot.json"]
        )
        self.assertEqual(
            config["secret_files"], ["auth/codex.json", "auth/copilot.json"]
        )

    def test_service_factory_creates_valid_service(self):
        service = ConfigFactory.service("test-service", 8080)

        self.assertIn("command", service)
        self.assertIn("host", service)
        self.assertIn("port", service)
        self.assertIn("readiness_path", service)
        self.assertEqual(service["port"], 8080)
        self.assertEqual(service["host"], DEFAULT_SERVICE_HOST)

    def test_configs_are_mutable(self):
        config = ConfigFactory.minimal()
        config["custom_field"] = "custom_value"
        config["auth"]["providers"]["codex"] = {}

        self.assertEqual(config["custom_field"], "custom_value")
        self.assertIn("codex", config["auth"]["providers"])
