"""Error path tests for profile management module.

This module tests error handling in profile.py,
ensuring proper exception handling for profile activation and credential resolution.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flowgate.profile import activate_profile

import pytest


@pytest.mark.unit
class TestProfileErrorHandling(unittest.TestCase):
    """Test profile management error handling."""

    def _minimal_config_with_profiles(self) -> dict:
        """Return minimal config with profiles."""
        return {
            "paths": {
                "runtime_dir": tempfile.mkdtemp(),
                "active_config": "runtime/litellm.active.yaml",
                "state_file": "runtime/state.json",
                "log_file": "runtime/events.log",
            },
            "litellm_base": {
                "model_list": [
                    {
                        "model_name": "test-model",
                        "litellm_params": {"model": "openai/gpt-4"},
                    }
                ]
            },
            "profiles": {
                "default": {"litellm_settings": {"num_retries": 1}},
                "reliability": {"litellm_settings": {"num_retries": 3}},
            },
        }

    def test_unknown_profile_name(self):
        """Test KeyError when activating unknown profile."""
        config = self._minimal_config_with_profiles()
        with self.assertRaises(KeyError) as ctx:
            activate_profile(config, "nonexistent")
        self.assertIn("Unknown profile: nonexistent", str(ctx.exception))

    def test_credential_file_not_found(self):
        """Test ValueError when credential file does not exist."""
        config = self._minimal_config_with_profiles()
        config["credentials"] = {
            "upstream": {"openai": {"file": "/non/existent/key.txt"}}
        }
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = (
            "openai"
        )

        with self.assertRaises(ValueError) as ctx:
            activate_profile(config, "default")
        self.assertIn("Credential file not found", str(ctx.exception))
        self.assertIn("/non/existent/key.txt", str(ctx.exception))

    def test_credential_file_empty(self):
        """Test ValueError when credential file is empty."""
        # Create empty credential file
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        tmp.close()
        cred_path = Path(tmp.name)

        config = self._minimal_config_with_profiles()
        config["credentials"] = {"upstream": {"openai": {"file": str(cred_path)}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = (
            "openai"
        )

        try:
            with self.assertRaises(ValueError) as ctx:
                activate_profile(config, "default")
            self.assertIn("Credential file is empty", str(ctx.exception))
            self.assertIn(str(cred_path), str(ctx.exception))
        finally:
            cred_path.unlink(missing_ok=True)

    def test_credential_file_whitespace_only(self):
        """Test ValueError when credential file contains only whitespace."""
        # Create credential file with whitespace
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        tmp.write("   \n\t  \n")
        tmp.flush()
        tmp.close()
        cred_path = Path(tmp.name)

        config = self._minimal_config_with_profiles()
        config["credentials"] = {"upstream": {"openai": {"file": str(cred_path)}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = (
            "openai"
        )

        try:
            with self.assertRaises(ValueError) as ctx:
                activate_profile(config, "default")
            self.assertIn("Credential file is empty", str(ctx.exception))
        finally:
            cred_path.unlink(missing_ok=True)

    def test_unknown_api_key_ref(self):
        """Test ValueError when api_key_ref references unknown credential."""
        config = self._minimal_config_with_profiles()
        config["credentials"] = {"upstream": {"openai": {"file": "/path/to/key.txt"}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = (
            "unknown_ref"
        )

        with self.assertRaises(ValueError) as ctx:
            activate_profile(config, "default")
        self.assertIn("Unknown api_key_ref: unknown_ref", str(ctx.exception))

    def test_api_key_ref_not_string(self):
        """Test ValueError when api_key_ref is not a string."""
        config = self._minimal_config_with_profiles()
        config["credentials"] = {"upstream": {"openai": {"file": "/path/to/key.txt"}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = 123

        with self.assertRaises(ValueError) as ctx:
            activate_profile(config, "default")
        self.assertIn("api_key_ref must be a non-empty string", str(ctx.exception))

    def test_api_key_ref_empty_string(self):
        """Test ValueError when api_key_ref is empty string."""
        config = self._minimal_config_with_profiles()
        config["credentials"] = {"upstream": {"openai": {"file": "/path/to/key.txt"}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = ""

        with self.assertRaises(ValueError) as ctx:
            activate_profile(config, "default")
        self.assertIn("api_key_ref must be a non-empty string", str(ctx.exception))

    def test_api_key_ref_whitespace_only(self):
        """Test ValueError when api_key_ref is whitespace only."""
        config = self._minimal_config_with_profiles()
        config["credentials"] = {"upstream": {"openai": {"file": "/path/to/key.txt"}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = (
            "   "
        )

        with self.assertRaises(ValueError) as ctx:
            activate_profile(config, "default")
        self.assertIn("api_key_ref must be a non-empty string", str(ctx.exception))

    def test_successful_profile_activation_creates_files(self):
        """Test successful profile activation creates active_config and state_file."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")

        active_path, state_path = activate_profile(config, "default")

        self.assertTrue(active_path.exists())
        self.assertTrue(state_path.exists())

        # Verify active config content
        active_content = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertIn("model_list", active_content)
        self.assertIn("litellm_settings", active_content)
        self.assertEqual(active_content["litellm_settings"]["num_retries"], 1)

        # Verify state file content
        state_content = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state_content["current_profile"], "default")
        self.assertIn("updated_at", state_content)

    def test_profile_overlay_merges_correctly(self):
        """Test profile overlay merges with base correctly."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")

        # Add additional settings to profile
        config["profiles"]["reliability"]["litellm_settings"]["cooldown_time"] = 60

        active_path, _ = activate_profile(config, "reliability")

        active_content = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active_content["litellm_settings"]["num_retries"], 3)
        self.assertEqual(active_content["litellm_settings"]["cooldown_time"], 60)

    def test_credential_resolution_with_valid_file(self):
        """Test successful credential resolution from file."""
        # Create valid credential file
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        tmp.write("sk-test-key-123")
        tmp.flush()
        tmp.close()
        cred_path = Path(tmp.name)

        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["credentials"] = {"upstream": {"openai": {"file": str(cred_path)}}}
        config["litellm_base"]["model_list"][0]["litellm_params"]["api_key_ref"] = (
            "openai"
        )

        try:
            active_path, _ = activate_profile(config, "default")

            active_content = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(
                active_content["model_list"][0]["litellm_params"]["api_key"],
                "sk-test-key-123",
            )
            # api_key_ref should be removed after resolution
            self.assertNotIn(
                "api_key_ref", active_content["model_list"][0]["litellm_params"]
            )
        finally:
            cred_path.unlink(missing_ok=True)

    def test_multiple_models_with_same_credential_ref(self):
        """Test multiple models can reference the same credential (caching)."""
        # Create valid credential file
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        tmp.write("sk-shared-key-123")
        tmp.flush()
        tmp.close()
        cred_path = Path(tmp.name)

        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["credentials"] = {"upstream": {"openai": {"file": str(cred_path)}}}

        # Add multiple models with same api_key_ref
        config["litellm_base"]["model_list"] = [
            {
                "model_name": "model-1",
                "litellm_params": {"model": "openai/gpt-4", "api_key_ref": "openai"},
            },
            {
                "model_name": "model-2",
                "litellm_params": {
                    "model": "openai/gpt-4-turbo",
                    "api_key_ref": "openai",
                },
            },
        ]

        try:
            active_path, _ = activate_profile(config, "default")

            active_content = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(
                active_content["model_list"][0]["litellm_params"]["api_key"],
                "sk-shared-key-123",
            )
            self.assertEqual(
                active_content["model_list"][1]["litellm_params"]["api_key"],
                "sk-shared-key-123",
            )
        finally:
            cred_path.unlink(missing_ok=True)

    def test_model_list_not_list(self):
        """Test graceful handling when model_list is not a list."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["litellm_base"]["model_list"] = "not-a-list"

        # Should not raise, just skip credential resolution
        active_path, _ = activate_profile(config, "default")
        self.assertTrue(active_path.exists())

    def test_model_item_not_dict(self):
        """Test graceful handling when model item is not a dict."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["litellm_base"]["model_list"] = ["not-a-dict"]

        # Should not raise, just skip this item
        active_path, _ = activate_profile(config, "default")
        self.assertTrue(active_path.exists())

    def test_litellm_params_not_dict(self):
        """Test graceful handling when litellm_params is not a dict."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["litellm_base"]["model_list"] = [
            {"model_name": "test", "litellm_params": "not-a-dict"}
        ]

        # Should not raise, just skip this item
        active_path, _ = activate_profile(config, "default")
        self.assertTrue(active_path.exists())

    def test_credentials_not_dict(self):
        """Test graceful handling when credentials is not a dict."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["credentials"] = "not-a-dict"

        # Should not raise, just skip credential resolution
        active_path, _ = activate_profile(config, "default")
        self.assertTrue(active_path.exists())

    def test_credentials_upstream_not_dict(self):
        """Test graceful handling when credentials.upstream is not a dict."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")
        config["credentials"] = {"upstream": "not-a-dict"}

        # Should not raise, just skip credential resolution
        active_path, _ = activate_profile(config, "default")
        self.assertTrue(active_path.exists())

    def test_custom_timestamp_in_state_file(self):
        """Test activate_profile accepts custom timestamp."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")

        custom_timestamp = "2024-01-15T10:30:00Z"
        _, state_path = activate_profile(
            config, "default", now_iso=custom_timestamp
        )

        state_content = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state_content["updated_at"], custom_timestamp)

    def test_atomic_write_uses_temp_file(self):
        """Test atomic write creates temp file and replaces atomically."""
        runtime_dir = Path(tempfile.mkdtemp())
        config = self._minimal_config_with_profiles()
        config["paths"]["runtime_dir"] = str(runtime_dir)
        config["paths"]["active_config"] = str(runtime_dir / "litellm.active.yaml")
        config["paths"]["state_file"] = str(runtime_dir / "state.json")

        active_path, _ = activate_profile(config, "default")

        # Verify no .tmp files left behind
        tmp_files = list(runtime_dir.rglob("*.tmp"))
        self.assertEqual(len(tmp_files), 0)

        # Verify final file exists
        self.assertTrue(active_path.exists())


if __name__ == "__main__":
    unittest.main()
