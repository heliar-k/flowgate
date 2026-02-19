"""
Tests for config migrate command.

This module tests the configuration migration from version 1 to version 2.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from flowgate.cli import run_cli


class TestConfigMigrate(unittest.TestCase):
    """Test config migrate command."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def _create_minimal_v1_config(self) -> dict:
        """Create minimal valid version 1 config."""
        return {
            "config_version": 1,
            "paths": {
                "runtime_dir": ".router/runtime",
                "active_config": ".router/runtime/active_litellm_config.yaml",
                "state_file": ".router/runtime/state.json",
                "log_file": ".router/runtime/events.log",
            },
            "services": {
                "litellm": {
                    "command": {"args": ["uv", "run", "litellm"]},
                    "host": "127.0.0.1",
                    "port": 4000,
                },
                "cliproxyapi": {
                    "command": {"args": [".router/bin/cliproxyapi"]},
                    "host": "127.0.0.1",
                    "port": 9000,
                },
            },
            "litellm_base": {
                "model_list": [],
                "router_settings": {},
                "litellm_settings": {},
            },
            "profiles": {
                "default": {
                    "litellm_settings": {},
                }
            },
            "oauth": {
                "codex": {
                    "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                    "status_endpoint": "http://127.0.0.1:9000/status",
                }
            },
            "secrets": ["auth/codex.json"],
        }

    def _create_minimal_v2_config(self) -> dict:
        """Create minimal valid version 2 config."""
        return {
            "config_version": 2,
            "paths": {
                "runtime_dir": ".router/runtime",
                "active_config": ".router/runtime/active_litellm_config.yaml",
                "state_file": ".router/runtime/state.json",
                "log_file": ".router/runtime/events.log",
            },
            "services": {
                "litellm": {
                    "command": {"args": ["uv", "run", "litellm"]},
                    "host": "127.0.0.1",
                    "port": 4000,
                },
                "cliproxyapi_plus": {
                    "command": {"args": [".router/bin/cliproxyapi"]},
                    "host": "127.0.0.1",
                    "port": 9000,
                },
            },
            "litellm_base": {
                "model_list": [],
                "router_settings": {},
                "litellm_settings": {},
            },
            "profiles": {
                "default": {
                    "litellm_settings": {},
                }
            },
            "auth": {
                "providers": {
                    "codex": {
                        "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
                        "status_endpoint": "http://127.0.0.1:9000/status",
                    }
                }
            },
            "secret_files": ["auth/codex.json"],
        }

    def test_migrate_v1_to_v2_json(self):
        """Test migrating version 1 to version 2 (JSON format)."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Configuration migrated successfully", output)
        self.assertIn("backup", output.lower())

        # Load migrated config
        with open(config_path) as f:
            migrated = json.load(f)

        # Verify migrations
        self.assertEqual(migrated["config_version"], 2)
        self.assertIn("auth", migrated)
        self.assertIn("providers", migrated["auth"])
        self.assertNotIn("oauth", migrated)
        self.assertIn("secret_files", migrated)
        self.assertNotIn("secrets", migrated)
        self.assertIn("cliproxyapi_plus", migrated["services"])
        self.assertNotIn("cliproxyapi", migrated["services"])

        # Verify backup was created
        backup_files = list(self.temp_path.glob("flowgate.json.backup-*"))
        self.assertEqual(len(backup_files), 1)

    def test_migrate_v1_to_v2_yaml(self):
        """Test migrating version 1 to version 2 (YAML format)."""
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError:
            self.skipTest("PyYAML not installed")

        config_path = self.temp_path / "flowgate.yaml"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            yaml.safe_dump(v1_config, f)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Configuration migrated successfully", output)

        # Load migrated config
        with open(config_path) as f:
            migrated = yaml.safe_load(f)

        # Verify migrations
        self.assertEqual(migrated["config_version"], 2)
        self.assertIn("auth", migrated)
        self.assertNotIn("oauth", migrated)

    def test_migrate_already_v2_no_op(self):
        """Test migrating version 2 config is a no-op."""
        config_path = self.temp_path / "flowgate.json"
        v2_config = self._create_minimal_v2_config()

        # Write v2 config
        with open(config_path, "w") as f:
            json.dump(v2_config, f, indent=2)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success with no-op message
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("already at version 2", output)
        self.assertIn("No migration needed", output)

        # Verify no backup was created
        backup_files = list(self.temp_path.glob("flowgate.json.backup-*"))
        self.assertEqual(len(backup_files), 0)

    def test_migrate_dry_run_no_changes(self):
        """Test dry-run mode doesn't modify config."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Get original content
        original_content = config_path.read_text()

        # Run migration with dry-run
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate", "--dry-run"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()
        self.assertIn("Dry-run mode", output)
        self.assertIn("Migration changes:", output)

        # Verify config unchanged
        current_content = config_path.read_text()
        self.assertEqual(original_content, current_content)

        # Verify no backup was created
        backup_files = list(self.temp_path.glob("flowgate.json.backup-*"))
        self.assertEqual(len(backup_files), 0)

    def test_migrate_creates_backup(self):
        """Test backup creation before migration."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        original_content = config_path.read_text()

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)

        # Verify backup was created
        backup_files = list(self.temp_path.glob("flowgate.json.backup-*"))
        self.assertEqual(len(backup_files), 1)

        # Verify backup content matches original
        backup_content = backup_files[0].read_text()
        self.assertEqual(original_content, backup_content)

    def test_migrate_oauth_to_auth_providers(self):
        """Test oauth → auth.providers migration."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)

        # Load migrated config
        with open(config_path) as f:
            migrated = json.load(f)

        # Verify oauth → auth.providers
        self.assertNotIn("oauth", migrated)
        self.assertIn("auth", migrated)
        self.assertIn("providers", migrated["auth"])
        self.assertIn("codex", migrated["auth"]["providers"])
        self.assertEqual(
            migrated["auth"]["providers"]["codex"]["auth_url_endpoint"],
            "http://127.0.0.1:9000/auth-url",
        )

    def test_migrate_secrets_to_secret_files(self):
        """Test secrets → secret_files migration."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)

        # Load migrated config
        with open(config_path) as f:
            migrated = json.load(f)

        # Verify secrets → secret_files
        self.assertNotIn("secrets", migrated)
        self.assertIn("secret_files", migrated)
        self.assertEqual(migrated["secret_files"], ["auth/codex.json"])

    def test_migrate_cliproxyapi_to_cliproxyapi_plus(self):
        """Test cliproxyapi → cliproxyapi_plus migration."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)

        # Load migrated config
        with open(config_path) as f:
            migrated = json.load(f)

        # Verify cliproxyapi → cliproxyapi_plus
        self.assertNotIn("cliproxyapi", migrated["services"])
        self.assertIn("cliproxyapi_plus", migrated["services"])
        self.assertEqual(
            migrated["services"]["cliproxyapi_plus"]["port"],
            9000,
        )

    def test_migrate_shows_all_changes(self):
        """Test migration output shows all detected changes."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration with dry-run to see changes
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate", "--dry-run"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)
        output = stdout.getvalue()

        # Verify all changes are listed
        self.assertIn("config_version: 2", output)
        self.assertIn("'secrets'", output)
        self.assertIn("'secret_files'", output)
        self.assertIn("cliproxyapi", output)
        self.assertIn("cliproxyapi_plus", output)
        self.assertIn("'oauth'", output)
        self.assertIn("'auth.providers'", output)

    def test_migrate_with_both_oauth_and_auth(self):
        """Test migration when both oauth and auth exist."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Add both oauth and auth
        v1_config["auth"] = {
            "providers": {
                "copilot": {
                    "auth_url_endpoint": "http://127.0.0.1:9000/copilot-auth",
                    "status_endpoint": "http://127.0.0.1:9000/copilot-status",
                }
            }
        }

        # Write config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check success
        self.assertEqual(exit_code, 0)

        # Load migrated config
        with open(config_path) as f:
            migrated = json.load(f)

        # Verify oauth removed, auth kept
        self.assertNotIn("oauth", migrated)
        self.assertIn("auth", migrated)
        self.assertIn("copilot", migrated["auth"]["providers"])

    def test_migrate_invalid_target_version(self):
        """Test migration with invalid target version."""
        config_path = self.temp_path / "flowgate.json"
        v1_config = self._create_minimal_v1_config()

        # Write v1 config
        with open(config_path, "w") as f:
            json.dump(v1_config, f, indent=2)

        # Run migration with invalid target
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate", "--to-version", "3"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check failure
        self.assertEqual(exit_code, 2)
        error_output = stderr.getvalue()
        self.assertIn("Unsupported target version", error_output)

    def test_migrate_missing_config_file(self):
        """Test migration with missing config file."""
        config_path = self.temp_path / "nonexistent.json"

        # Run migration
        stdout = StringIO()
        stderr = StringIO()
        exit_code = run_cli(
            ["--config", str(config_path), "config", "migrate"],
            stdout=stdout,
            stderr=stderr,
        )

        # Check failure
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
