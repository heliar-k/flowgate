"""
Config command handlers for FlowGate CLI.

This module contains command handlers for configuration operations including
migration from version 1 to version 2.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from ...config import ConfigError, load_router_config
from ..error_handler import handle_command_errors
from .base import BaseCommand


class ConfigMigrateCommand(BaseCommand):
    """Migrate configuration from version 1 to version 2."""

    @handle_command_errors
    def execute(self) -> int:
        """Execute config migrate command."""
        stdout: TextIO = getattr(self.args, "stdout", None) or sys.stdout
        stderr: TextIO = getattr(self.args, "stderr", None) or sys.stderr

        config_path = Path(self.args.config)
        target_version = getattr(self.args, "to_version", 2)
        dry_run = getattr(self.args, "dry_run", False)

        if target_version != 2:
            print(f"❌ Unsupported target version: {target_version}", file=stderr)
            print("   Only version 2 is supported", file=stderr)
            return 2

        # Load raw config file
        try:
            data = self._load_raw_config(config_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"❌ Failed to load config: {exc}", file=stderr)
            return 2

        # Check current version
        current_version = data.get("config_version", 1)

        print("📋 Analyzing configuration...", file=stdout)
        print(f"   Current version: {current_version}", file=stdout)
        print(f"   Target version: {target_version}", file=stdout)
        print("", file=stdout)

        # Check if migration is needed
        changes = self._detect_changes(data)
        if not changes:
            print("✅ Configuration is already at version 2", file=stdout)
            print("   No migration needed", file=stdout)
            return 0

        # Show migration plan
        print("🔄 Migration changes:", file=stdout)
        for change in changes:
            print(f"   - {change}", file=stdout)
        print("", file=stdout)

        # Dry-run mode
        if dry_run:
            print("🔍 Dry-run mode: No changes will be written", file=stdout)
            return 0

        # Create backup
        try:
            backup_path = self._create_backup(config_path)
            print(f"💾 Creating backup: {backup_path}", file=stdout)
        except OSError as exc:
            print(f"❌ Failed to create backup: {exc}", file=stderr)
            return 1

        # Perform migration
        migrated = self._migrate_to_v2(data)

        # Write migrated config
        try:
            self._write_config(config_path, migrated)
        except OSError as exc:
            print(f"❌ Failed to write migrated config: {exc}", file=stderr)
            return 1

        # Validate migrated config
        try:
            load_router_config(config_path)
        except ConfigError as exc:
            print(f"❌ Migration validation failed: {exc}", file=stderr)
            print(f"   Restoring from backup: {backup_path}", file=stderr)
            try:
                backup_path.rename(config_path)
            except OSError:
                pass
            return 1

        print("✅ Configuration migrated successfully!", file=stdout)
        print(f"   New config: {config_path}", file=stdout)
        print(f"   Backup: {backup_path}", file=stdout)
        return 0

    def _load_raw_config(self, path: Path) -> dict[str, Any]:
        """Load raw config file without normalization."""
        text = path.read_text(encoding="utf-8")

        # Try YAML first
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(text)
        except ModuleNotFoundError:
            # Fall back to JSON
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "PyYAML is not installed and config is not valid JSON"
                ) from exc

        if not isinstance(data, dict):
            raise ValueError("Config must be a mapping/object")

        return data

    def _detect_changes(self, data: dict[str, Any]) -> list[str]:
        """Detect what changes are needed for migration."""
        changes = []

        current_version = data.get("config_version", 1)
        if current_version != 2:
            changes.append("Set 'config_version: 2'")

        if "secrets" in data:
            changes.append("Rename 'secrets' → 'secret_files'")

        services = data.get("services", {})
        if isinstance(services, dict) and "cliproxyapi" in services:
            changes.append("Rename 'services.cliproxyapi' → 'services.cliproxyapi_plus'")

        if "oauth" in data and "auth" not in data:
            changes.append("Rename 'oauth' → 'auth.providers'")
        elif "oauth" in data and "auth" in data:
            changes.append("Remove 'oauth' (already have 'auth.providers')")

        return changes

    def _migrate_to_v2(self, data: dict[str, Any]) -> dict[str, Any]:
        """Migrate config to version 2."""
        migrated = dict(data)

        # Set version
        migrated["config_version"] = 2

        # Migrate secrets → secret_files
        if "secrets" in migrated:
            migrated["secret_files"] = migrated.pop("secrets")

        # Migrate cliproxyapi → cliproxyapi_plus
        if "services" in migrated:
            services = migrated["services"]
            if isinstance(services, dict) and "cliproxyapi" in services:
                services["cliproxyapi_plus"] = services.pop("cliproxyapi")

        # Migrate oauth → auth.providers
        if "oauth" in migrated and "auth" not in migrated:
            migrated["auth"] = {"providers": migrated.pop("oauth")}
        elif "oauth" in migrated:
            # Both exist - remove oauth, keep auth
            migrated.pop("oauth")

        return migrated

    def _create_backup(self, config_path: Path) -> Path:
        """Create backup of config file."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = config_path.with_suffix(f"{config_path.suffix}.backup-{timestamp}")

        # Copy original to backup
        backup_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

        return backup_path

    def _write_config(self, path: Path, data: dict[str, Any]) -> None:
        """Write config file in appropriate format."""
        if path.suffix in [".yaml", ".yml"]:
            try:
                import yaml  # type: ignore
                with open(path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            except ModuleNotFoundError:
                # Fall back to JSON if YAML not available
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
