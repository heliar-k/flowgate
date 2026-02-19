"""Unit tests for PathResolver class."""

import json
import tempfile
import unittest
from pathlib import Path

from flowgate.config_utils.path_resolver import PathResolver


class TestPathResolverInit(unittest.TestCase):
    """Test PathResolver initialization."""

    def test_init_with_absolute_path(self):
        """Test initialization with absolute config path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config" / "flowgate.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.touch()

            resolver = PathResolver(config_path)

            self.assertEqual(resolver.config_dir, config_path.parent.resolve())
            self.assertTrue(resolver.config_dir.is_absolute())

    def test_init_with_relative_path(self):
        """Test initialization with relative config path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config in temp dir
            config_path = Path(temp_dir) / "config" / "flowgate.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.touch()

            # Use relative path from temp dir
            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                relative_path = Path("config/flowgate.yaml")

                resolver = PathResolver(relative_path)

                # Should resolve to absolute path
                self.assertTrue(resolver.config_dir.is_absolute())
                self.assertEqual(
                    resolver.config_dir, (Path(temp_dir) / "config").resolve()
                )
            finally:
                os.chdir(original_cwd)


class TestPathResolverResolve(unittest.TestCase):
    """Test resolve() method."""

    def setUp(self):
        """Create temporary test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config" / "flowgate.yaml"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.touch()
        self.resolver = PathResolver(self.config_path)

    def tearDown(self):
        """Clean up temporary test environment."""
        self.temp_dir.cleanup()

    def test_resolve_absolute_path(self):
        """Test resolving absolute path returns unchanged."""
        abs_path = "/var/log/app.log"
        result = self.resolver.resolve(abs_path)
        self.assertEqual(result, abs_path)

    def test_resolve_relative_path(self):
        """Test resolving relative path relative to config directory."""
        rel_path = "logs/app.log"
        result = self.resolver.resolve(rel_path)
        expected = str((self.config_path.parent / rel_path).resolve())
        self.assertEqual(result, expected)

    def test_resolve_relative_path_with_parent_dir(self):
        """Test resolving relative path with .. parent directory."""
        rel_path = "../data/file.txt"
        result = self.resolver.resolve(rel_path)
        expected = str((self.config_path.parent / rel_path).resolve())
        self.assertEqual(result, expected)

    def test_resolve_current_directory(self):
        """Test resolving . current directory."""
        rel_path = "."
        result = self.resolver.resolve(rel_path)
        expected = str(self.config_path.parent.resolve())
        self.assertEqual(result, expected)

    def test_resolve_nested_relative_path(self):
        """Test resolving deeply nested relative path."""
        rel_path = "a/b/c/d/file.txt"
        result = self.resolver.resolve(rel_path)
        expected = str((self.config_path.parent / rel_path).resolve())
        self.assertEqual(result, expected)


class TestPathResolverResolveConfigPaths(unittest.TestCase):
    """Test resolve_config_paths() method."""

    def setUp(self):
        """Create temporary test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config" / "flowgate.yaml"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.touch()
        self.resolver = PathResolver(self.config_path)

    def tearDown(self):
        """Clean up temporary test environment."""
        self.temp_dir.cleanup()

    def test_resolve_paths_fields(self):
        """Test resolving all paths.* fields."""
        config = {
            "paths": {
                "runtime_dir": ".router",
                "active_config": ".router/litellm.active.yaml",
                "state_file": ".router/state.json",
                "log_file": "logs/app.log",
            }
        }

        resolved = self.resolver.resolve_config_paths(config)

        # All paths should be resolved
        for key, value in resolved["paths"].items():
            self.assertTrue(Path(value).is_absolute())
            # Original relative paths should be resolved relative to config dir
            if not Path(config["paths"][key]).is_absolute():
                expected = str(
                    (self.config_path.parent / config["paths"][key]).resolve()
                )
                self.assertEqual(value, expected)

    def test_resolve_secret_files_list(self):
        """Test resolving secret_files list."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "secret_files": ["secrets/api.key", "secrets/oauth.json"],
        }

        resolved = self.resolver.resolve_config_paths(config)

        self.assertEqual(len(resolved["secret_files"]), 2)
        for path in resolved["secret_files"]:
            self.assertTrue(Path(path).is_absolute())

    def test_resolve_credentials_upstream_file(self):
        """Test resolving credentials.upstream.*.file paths."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "credentials": {
                "upstream": {
                    "openai": {"file": "creds/openai.key"},
                    "anthropic": {"file": "creds/anthropic.key"},
                }
            },
        }

        resolved = self.resolver.resolve_config_paths(config)

        openai_file = resolved["credentials"]["upstream"]["openai"]["file"]
        anthropic_file = resolved["credentials"]["upstream"]["anthropic"]["file"]

        self.assertTrue(Path(openai_file).is_absolute())
        self.assertTrue(Path(anthropic_file).is_absolute())
        self.assertIn("creds/openai.key", openai_file)
        self.assertIn("creds/anthropic.key", anthropic_file)

    def test_resolve_services_command_cwd(self):
        """Test resolving services.*.command.cwd paths."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "services": {
                "litellm": {"command": {"cwd": "runtime/litellm", "args": ["litellm"]}},
                "cliproxyapi_plus": {
                    "command": {"cwd": "runtime/cliproxy", "args": ["cliproxy"]}
                },
            },
        }

        resolved = self.resolver.resolve_config_paths(config)

        litellm_cwd = resolved["services"]["litellm"]["command"]["cwd"]
        cliproxy_cwd = resolved["services"]["cliproxyapi_plus"]["command"]["cwd"]

        self.assertTrue(Path(litellm_cwd).is_absolute())
        self.assertTrue(Path(cliproxy_cwd).is_absolute())

    def test_resolve_minimal_config(self):
        """Test resolving minimal configuration with only required fields."""
        config = {
            "paths": {
                "runtime_dir": ".router",
            }
        }

        resolved = self.resolver.resolve_config_paths(config)

        self.assertIn("paths", resolved)
        self.assertTrue(Path(resolved["paths"]["runtime_dir"]).is_absolute())

    def test_resolve_missing_secret_files(self):
        """Test resolving config without secret_files field."""
        config = {
            "paths": {"runtime_dir": ".router"},
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Should create empty list if missing
        self.assertEqual(resolved["secret_files"], [])

    def test_resolve_missing_credentials(self):
        """Test resolving config without credentials field."""
        config = {
            "paths": {"runtime_dir": ".router"},
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Should not crash, credentials field may not exist
        self.assertNotIn("credentials", resolved)

    def test_resolve_missing_services_cwd(self):
        """Test resolving services without command.cwd field."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "services": {
                "litellm": {
                    "command": {
                        "args": ["litellm"],
                        # No cwd field
                    }
                }
            },
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Should not crash, cwd is optional
        self.assertNotIn("cwd", resolved["services"]["litellm"]["command"])

    def test_resolve_mixed_absolute_and_relative_paths(self):
        """Test resolving config with mixed absolute and relative paths."""
        config = {
            "paths": {
                "runtime_dir": "/absolute/path/runtime",
                "active_config": "relative/config.yaml",
                "state_file": "/absolute/state.json",
                "log_file": "relative/logs/app.log",
            },
            "secret_files": ["/absolute/secret.key", "relative/secret.json"],
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Absolute paths should remain unchanged
        self.assertEqual(
            resolved["paths"]["runtime_dir"], "/absolute/path/runtime"
        )
        self.assertEqual(resolved["paths"]["state_file"], "/absolute/state.json")
        self.assertEqual(resolved["secret_files"][0], "/absolute/secret.key")

        # Relative paths should be resolved
        self.assertTrue(Path(resolved["paths"]["active_config"]).is_absolute())
        self.assertTrue(Path(resolved["paths"]["log_file"]).is_absolute())
        self.assertTrue(Path(resolved["secret_files"][1]).is_absolute())

    def test_resolve_does_not_modify_original_config(self):
        """Test that resolve_config_paths does not modify original config."""
        config = {
            "paths": {
                "runtime_dir": ".router",
                "active_config": ".router/config.yaml",
            },
            "secret_files": ["secrets/api.key"],
            "credentials": {
                "upstream": {
                    "openai": {"file": "creds/openai.key"},
                }
            },
            "services": {
                "litellm": {"command": {"cwd": "runtime", "args": ["litellm"]}}
            },
        }

        # Create deep copy for comparison
        original_config = json.loads(json.dumps(config))

        # Resolve paths
        resolved = self.resolver.resolve_config_paths(config)

        # Original config should be unchanged
        self.assertEqual(config, original_config)

        # Resolved config should be different
        self.assertNotEqual(resolved["paths"]["runtime_dir"], config["paths"]["runtime_dir"])
        self.assertNotEqual(resolved["secret_files"][0], config["secret_files"][0])

    def test_resolve_empty_secret_files_list(self):
        """Test resolving config with empty secret_files list."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "secret_files": [],
        }

        resolved = self.resolver.resolve_config_paths(config)

        self.assertEqual(resolved["secret_files"], [])

    def test_resolve_credentials_with_non_dict_entry(self):
        """Test resolving credentials with non-dict upstream entry."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "credentials": {
                "upstream": {
                    "openai": {"file": "creds/openai.key"},
                    "invalid": "not_a_dict",  # Should be skipped
                }
            },
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Valid entry should be resolved
        self.assertTrue(
            Path(resolved["credentials"]["upstream"]["openai"]["file"]).is_absolute()
        )
        # Invalid entry should remain unchanged
        self.assertEqual(resolved["credentials"]["upstream"]["invalid"], "not_a_dict")

    def test_resolve_credentials_without_file_field(self):
        """Test resolving credentials entry without file field."""
        config = {
            "paths": {"runtime_dir": ".router"},
            "credentials": {
                "upstream": {
                    "openai": {"api_key": "sk-xxx"},  # No file field
                }
            },
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Should not crash, file field is optional
        self.assertNotIn("file", resolved["credentials"]["upstream"]["openai"])
        self.assertEqual(
            resolved["credentials"]["upstream"]["openai"]["api_key"], "sk-xxx"
        )

    def test_resolve_all_path_types_together(self):
        """Test resolving all path types in a single config."""
        config = {
            "paths": {
                "runtime_dir": ".router",
                "active_config": ".router/config.yaml",
                "state_file": ".router/state.json",
                "log_file": "logs/app.log",
            },
            "secret_files": ["secrets/api.key", "secrets/oauth.json"],
            "credentials": {
                "upstream": {
                    "openai": {"file": "creds/openai.key"},
                    "anthropic": {"file": "creds/anthropic.key"},
                }
            },
            "services": {
                "litellm": {"command": {"cwd": "runtime/litellm", "args": ["litellm"]}},
                "cliproxyapi_plus": {
                    "command": {"cwd": "runtime/cliproxy", "args": ["cliproxy"]}
                },
            },
        }

        resolved = self.resolver.resolve_config_paths(config)

        # Verify all path types are resolved
        # 1. paths.*
        for value in resolved["paths"].values():
            self.assertTrue(Path(value).is_absolute())

        # 2. secret_files
        for path in resolved["secret_files"]:
            self.assertTrue(Path(path).is_absolute())

        # 3. credentials.upstream.*.file
        for entry in resolved["credentials"]["upstream"].values():
            if "file" in entry:
                self.assertTrue(Path(entry["file"]).is_absolute())

        # 4. services.*.command.cwd
        for service in resolved["services"].values():
            if "cwd" in service["command"]:
                self.assertTrue(Path(service["command"]["cwd"]).is_absolute())


if __name__ == "__main__":
    unittest.main()
