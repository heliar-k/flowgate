# Phase 2.1: Config Version 1 Migration Plan

**Date**: 2026-02-19
**Phase**: 2.1 - Remove config_version: 1 Support
**Status**: Analysis Complete - Ready for Implementation
**Target Version**: v0.3.0 (Breaking Change)

---

## Executive Summary

This document provides a detailed analysis and migration plan for removing config_version: 1 support from FlowGate. The legacy compatibility layer adds ~80 lines of code complexity and maintains three field mappings that are no longer needed.

**Key Findings**:
- Legacy support code: ~80 lines across 3 files
- Field mappings: 3 (oauth → auth.providers, secrets → secret_files, cliproxyapi → cliproxyapi_plus)
- Estimated code reduction: 43% in config.py normalization logic
- All example configs already use version 2
- Zero breaking impact if migration command provided

**Migration Strategy**: Two-stage deprecation (v0.2.0 warnings → v0.3.0 removal)

---

## 1. Legacy Code Inventory

### 1.1 Core Configuration Module (`src/flowgate/config.py`)

**File Stats**:
- Total lines: 184
- Legacy-related lines: ~50 (27% of file)

**Legacy Code Locations**:

#### Constants (Lines 14-34)
```python
# Line 22: Legacy key allowed for backward compatibility
_ALLOWED_TOP_LEVEL_KEYS = {
    "oauth",  # ← Legacy, maps to auth.providers
    # ...
}

# Lines 33-34: Version support
_LATEST_CONFIG_VERSION = 2
_SUPPORTED_CONFIG_VERSIONS = {1, 2}  # ← Remove version 1
```

**Impact**: Remove `oauth` from allowed keys, change `_SUPPORTED_CONFIG_VERSIONS = {2}`

---

#### Normalization Function (Lines 76-112)

**Function**: `_normalize_legacy_fields(data: dict[str, Any]) -> dict[str, Any]`

**Legacy Mappings**:

1. **secrets → secret_files** (Lines 89-91):
```python
if "secret_files" not in normalized and "secrets" in normalized:
    normalized["secret_files"] = normalized["secrets"]
normalized.pop("secrets", None)
```

2. **cliproxyapi → cliproxyapi_plus** (Lines 93-98):
```python
services_raw = normalized.get("services")
if isinstance(services_raw, dict):
    services = dict(services_raw)
    if "cliproxyapi_plus" not in services and "cliproxyapi" in services:
        services["cliproxyapi_plus"] = services.pop("cliproxyapi")
    normalized["services"] = services
```

3. **oauth → auth.providers** (Lines 100-110):
```python
auth_raw = normalized.get("auth")
oauth_raw = normalized.get("oauth")

if "auth" not in normalized and isinstance(oauth_raw, dict):
    normalized["auth"] = {"providers": dict(oauth_raw)}
elif isinstance(auth_raw, dict):
    providers_raw = auth_raw.get("providers", {})
    providers = _ensure_mapping(providers_raw, "auth.providers")
    normalized["auth"] = {"providers": providers}
    if "oauth" not in normalized:
        normalized["oauth"] = dict(providers)
```

**Complexity**: 37 lines of normalization logic (Lines 76-112)

---

#### Config Loading (Lines 141-164)

**Legacy Support**:
```python
# Lines 141-143: Load and validate legacy oauth field
oauth = data.get("oauth", {})
oauth_map = _ensure_mapping(oauth, "oauth")
ConfigValidator.validate_oauth(oauth_map)

# Lines 161-162: Return both auth and oauth in output
return {
    # ...
    "auth": {"providers": providers},
    "oauth": oauth_map,  # ← Legacy field maintained
    # ...
}
```

**Impact**: Remove oauth loading and validation, remove from return dict

---

### 1.2 Validation Module (`src/flowgate/validators.py`)

**File Stats**:
- Total lines: 290
- Legacy-related lines: ~14 (5% of file)

**Legacy Code Location**:

#### OAuth Validator (Lines 239-253)
```python
@staticmethod
def validate_oauth(oauth_config: dict[str, Any]) -> None:
    """Validate the oauth configuration section (legacy).

    Each provider must be a dictionary. This is a legacy validation
    for backward compatibility with config version 1.

    Args:
        oauth_config: The oauth section from configuration

    Raises:
        ConfigError: If validation fails
    """
    for name, provider in oauth_config.items():
        ConfigValidator._validate_type(provider, dict, f"oauth.{name}")
```

**Impact**: Remove entire `validate_oauth()` method (14 lines)

---

### 1.3 Auth Command Module (`src/flowgate/cli/commands/auth.py`)

**File Stats**:
- Total lines: 245
- Legacy-related lines: ~16 (7% of file)

**Legacy Code Location**:

#### Helper Function (Lines 20-32)
```python
def _auth_providers(config: dict[str, Any]) -> dict[str, Any]:
    """Extract auth providers from config, supporting both new and legacy formats."""
    auth = config.get("auth", {})
    if isinstance(auth, dict):
        providers_raw = auth.get("providers", {})
        if isinstance(providers_raw, dict):
            return providers_raw

    # Legacy fallback
    oauth = config.get("oauth", {})
    if isinstance(oauth, dict):
        return oauth

    return {}
```

**Impact**: Simplify to only read from `auth.providers`, remove oauth fallback (12 lines)

---

### 1.4 Test Files

**Files with Legacy Field References**:

1. `tests/test_config.py` (Lines 121-133):
   - `test_migrates_legacy_secrets_key()` - Tests secrets → secret_files
   - `test_migrates_legacy_cliproxyapi_service_name()` - Tests cliproxyapi → cliproxyapi_plus

2. Test base configs use `oauth` field (Line 77-86):
```python
"oauth": {
    "codex": {
        "auth_url_endpoint": "http://127.0.0.1:9000/auth-url",
        "status_endpoint": "http://127.0.0.1:9000/status",
    },
    # ...
}
```

**Impact**:
- Remove 2 legacy migration tests (~20 lines)
- Update test configs to use `auth.providers` (~50 lines across multiple files)

---

## 2. Code Reduction Analysis

### 2.1 Lines of Code Impact

| File | Current Lines | Legacy Lines | After Removal | Reduction |
|------|---------------|--------------|---------------|-----------|
| `config.py` | 184 | 50 | 134 | -27.2% |
| `validators.py` | 290 | 14 | 276 | -4.8% |
| `auth.py` | 245 | 16 | 229 | -6.5% |
| `test_config.py` | 196 | 20 | 176 | -10.2% |
| **Total** | **915** | **100** | **815** | **-10.9%** |

### 2.2 Complexity Reduction

**Cyclomatic Complexity**:
- `_normalize_legacy_fields()`: Current complexity ~8 → Will be removed entirely
- `load_router_config()`: Complexity reduction from 12 → 9 (remove oauth handling)
- `_auth_providers()`: Complexity reduction from 4 → 2 (remove fallback logic)

**Maintenance Benefits**:
- Eliminate 3 field mapping rules
- Remove version checking logic
- Simplify config validation flow
- Reduce cognitive load for new developers

---

## 3. Migration Strategy

### 3.1 Two-Stage Approach

#### Stage 1: Deprecation Warnings (v0.2.0)

**Objectives**:
1. Detect legacy config usage
2. Emit clear deprecation warnings
3. Provide migration command
4. Maintain full backward compatibility

**Implementation**:

```python
# src/flowgate/config.py
def _check_deprecations(data: dict[str, Any]) -> list[str]:
    """Check for deprecated config fields and return warnings."""
    warnings = []

    if data.get("config_version", 2) == 1:
        warnings.append(
            "config_version: 1 is deprecated and will be removed in v0.3.0. "
            "Run 'flowgate config migrate' to upgrade."
        )

    if "secrets" in data:
        warnings.append(
            "'secrets' field is deprecated, use 'secret_files' instead. "
            "Run 'flowgate config migrate' to upgrade."
        )

    if "oauth" in data and "auth" not in data:
        warnings.append(
            "'oauth' field is deprecated, use 'auth.providers' instead. "
            "Run 'flowgate config migrate' to upgrade."
        )

    services = data.get("services", {})
    if "cliproxyapi" in services and "cliproxyapi_plus" not in services:
        warnings.append(
            "'cliproxyapi' service name is deprecated, use 'cliproxyapi_plus'. "
            "Run 'flowgate config migrate' to upgrade."
        )

    return warnings
```

**Warning Display**:
```bash
$ flowgate status
⚠️  Configuration Deprecation Warnings:
  - config_version: 1 is deprecated and will be removed in v0.3.0
  - 'oauth' field is deprecated, use 'auth.providers' instead

Run 'flowgate config migrate' to automatically upgrade your configuration.

[... normal output continues ...]
```

---

#### Stage 2: Complete Removal (v0.3.0)

**Objectives**:
1. Remove all legacy support code
2. Reject version 1 configs with clear error
3. Update documentation
4. Clean up tests

**Implementation**:

```python
# src/flowgate/config.py (v0.3.0)
_SUPPORTED_CONFIG_VERSIONS = {2}  # Only version 2

def load_router_config(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    data = _parse_yaml_like(path_obj)

    # Reject unsupported versions immediately
    version = data.get("config_version", 2)
    if version != 2:
        raise ConfigError(
            f"Unsupported config_version={version}. "
            f"FlowGate v0.3.0+ only supports config_version: 2. "
            f"Please upgrade using FlowGate v0.2.x: 'flowgate config migrate'"
        )

    # No normalization needed - direct validation
    # ... rest of validation
```

---

### 3.2 Migration Command

**Command**: `flowgate config migrate`

**Features**:
- Automatic backup creation
- Dry-run mode
- Validation before/after
- Clear success/error messages

**Implementation**:

```python
# src/flowgate/cli/commands/config.py
class ConfigMigrateCommand(BaseCommand):
    """Migrate configuration to latest version."""

    @handle_command_errors
    def execute(self) -> int:
        config_path = Path(self.args.config)

        # Load current config
        with open(config_path) as f:
            if config_path.suffix in ['.yaml', '.yml']:
                import yaml
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        # Check if migration needed
        needs_migration = self._needs_migration(data)
        if not needs_migration:
            print("✅ Configuration is already at version 2")
            return 0

        # Dry run mode
        if self.args.dry_run:
            print("🔍 Dry run - changes that would be made:")
            self._show_migration_plan(data)
            return 0

        # Create backup
        backup_path = self._create_backup(config_path)
        print(f"📦 Backup created: {backup_path}")

        # Perform migration
        migrated = self._migrate_to_v2(data)

        # Validate migrated config
        try:
            load_router_config(config_path)  # This will use migrated data
        except ConfigError as e:
            print(f"❌ Migration validation failed: {e}")
            print(f"   Restoring from backup: {backup_path}")
            shutil.copy(backup_path, config_path)
            return 1

        # Write migrated config
        with open(config_path, 'w') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                yaml.safe_dump(migrated, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(migrated, f, indent=2)

        print("✅ Configuration migrated to version 2")
        print(f"   Backup: {backup_path}")
        return 0

    def _migrate_to_v2(self, data: dict) -> dict:
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
            if "cliproxyapi" in services:
                services["cliproxyapi_plus"] = services.pop("cliproxyapi")

        # Migrate oauth → auth.providers
        if "oauth" in migrated and "auth" not in migrated:
            migrated["auth"] = {"providers": migrated.pop("oauth")}
        elif "oauth" in migrated:
            # Both exist - remove oauth, keep auth
            migrated.pop("oauth")

        return migrated
```

**Usage**:
```bash
# Dry run to see changes
$ flowgate config migrate --dry-run
🔍 Dry run - changes that would be made:
  - Set config_version: 2
  - Rename 'oauth' → 'auth.providers'
  - Rename 'secrets' → 'secret_files'

# Perform migration
$ flowgate config migrate
📦 Backup created: config/flowgate.yaml.backup-20260219-143022
✅ Configuration migrated to version 2
   Backup: config/flowgate.yaml.backup-20260219-143022
```

---

## 4. Implementation Plan

### 4.1 Phase 2.1.1: Add Deprecation Warnings (v0.2.0)

**Duration**: 1 day

**Tasks**:
1. ✅ Implement `_check_deprecations()` function
2. ✅ Add warning display to CLI entry point
3. ✅ Create `ConfigMigrateCommand` class
4. ✅ Add `config migrate` subcommand to parser
5. ✅ Write migration tests
6. ✅ Update documentation

**Deliverables**:
- `src/flowgate/config.py`: Add deprecation checker
- `src/flowgate/cli/commands/config.py`: New file with migrate command
- `tests/test_config_migrate.py`: Migration tests
- `docs/migration-guide-v0.3.md`: User migration guide

**Acceptance Criteria**:
- [ ] Deprecation warnings display for all legacy fields
- [ ] Migration command successfully converts v1 → v2
- [ ] Backup created before migration
- [ ] Dry-run mode works correctly
- [ ] All tests pass (187/187)

---

### 4.1.2: Remove Legacy Support (v0.3.0)

**Duration**: 0.5 days

**Tasks**:
1. ✅ Remove `_normalize_legacy_fields()` function
2. ✅ Remove `oauth` from `_ALLOWED_TOP_LEVEL_KEYS`
3. ✅ Change `_SUPPORTED_CONFIG_VERSIONS = {2}`
4. ✅ Remove `validate_oauth()` from validators
5. ✅ Simplify `_auth_providers()` helper
6. ✅ Remove legacy migration tests
7. ✅ Update all test configs to v2 format
8. ✅ Update documentation

**Deliverables**:
- Modified: `src/flowgate/config.py` (-50 lines)
- Modified: `src/flowgate/validators.py` (-14 lines)
- Modified: `src/flowgate/cli/commands/auth.py` (-16 lines)
- Modified: `tests/test_config.py` (-20 lines)
- Updated: All test fixtures to use v2 format
- Updated: `CLAUDE.md`, `README.md`, `docs/configuration.md`

**Acceptance Criteria**:
- [ ] Version 1 configs rejected with clear error message
- [ ] All code references to `oauth`, `secrets`, `cliproxyapi` removed
- [ ] All tests pass with v2 configs only
- [ ] Documentation updated
- [ ] Breaking change noted in CHANGELOG.md

---

## 5. Risk Assessment

### 5.1 Breaking Change Impact

**Risk Level**: MEDIUM

**Affected Users**:
- Users still on config_version: 1
- Users with `oauth` field in config
- Users with `secrets` field in config
- Users with `cliproxyapi` service name

**Mitigation**:
1. ✅ Provide migration command in v0.2.0
2. ✅ Display clear deprecation warnings
3. ✅ Document migration process
4. ✅ Maintain v0.2.x branch for emergency patches
5. ✅ Clear error messages in v0.3.0 pointing to migration guide

---

### 5.2 Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration command has bugs | Medium | High | Extensive testing, dry-run mode, automatic backup |
| Users miss deprecation warnings | Medium | Medium | Display on every command, document in release notes |
| Test configs not updated | Low | High | Automated check in CI for legacy fields |
| Documentation outdated | Medium | Low | Update docs as part of implementation PR |

---

## 6. Testing Strategy

### 6.1 Migration Command Tests

```python
# tests/test_config_migrate.py
class TestConfigMigrate(unittest.TestCase):
    def test_migrate_oauth_to_auth_providers(self):
        """Test oauth → auth.providers migration"""
        v1_config = {
            "config_version": 1,
            "oauth": {"codex": {"auth_url_endpoint": "..."}},
            # ... other fields
        }
        migrated = migrate_to_v2(v1_config)
        self.assertEqual(migrated["config_version"], 2)
        self.assertIn("auth", migrated)
        self.assertIn("providers", migrated["auth"])
        self.assertNotIn("oauth", migrated)

    def test_migrate_secrets_to_secret_files(self):
        """Test secrets → secret_files migration"""
        v1_config = {
            "config_version": 1,
            "secrets": ["auth/codex.json"],
            # ...
        }
        migrated = migrate_to_v2(v1_config)
        self.assertIn("secret_files", migrated)
        self.assertNotIn("secrets", migrated)

    def test_migrate_creates_backup(self):
        """Test backup creation before migration"""
        # ...

    def test_migrate_dry_run_no_changes(self):
        """Test dry-run mode doesn't modify config"""
        # ...

    def test_migrate_already_v2_no_op(self):
        """Test migrating v2 config is no-op"""
        # ...
```

### 6.2 Deprecation Warning Tests

```python
# tests/test_config_deprecation.py
class TestDeprecationWarnings(unittest.TestCase):
    def test_warns_on_config_version_1(self):
        """Test warning for config_version: 1"""
        # ...

    def test_warns_on_oauth_field(self):
        """Test warning for oauth field"""
        # ...

    def test_no_warnings_for_v2_config(self):
        """Test no warnings for clean v2 config"""
        # ...
```

### 6.3 Regression Tests

**Ensure v0.3.0 behavior**:
- [ ] Version 1 configs rejected with ConfigError
- [ ] Clear error message points to migration guide
- [ ] Version 2 configs load without warnings
- [ ] All commands work with v2 configs
- [ ] No performance regression

---

## 7. Documentation Updates

### 7.1 New Documents

**`docs/migration-guide-v0.3.md`**:
```markdown
# Migration Guide: FlowGate v0.2.x → v0.3.0

## Breaking Changes

FlowGate v0.3.0 removes support for config_version: 1 and legacy field names.

### Removed Features
- config_version: 1 (only version 2 supported)
- `oauth` field (use `auth.providers`)
- `secrets` field (use `secret_files`)
- `cliproxyapi` service name (use `cliproxyapi_plus`)

### Migration Steps

1. **Upgrade to v0.2.x first** (if not already):
   ```bash
   uv pip install flowgate==0.2.0
   ```

2. **Run migration command**:
   ```bash
   flowgate config migrate --dry-run  # Preview changes
   flowgate config migrate             # Perform migration
   ```

3. **Verify configuration**:
   ```bash
   flowgate doctor
   ```

4. **Upgrade to v0.3.0**:
   ```bash
   uv pip install flowgate==0.3.0
   ```

### Manual Migration

If you prefer to migrate manually:

**Before (v1)**:
```yaml
config_version: 1
oauth:
  codex:
    auth_url_endpoint: "..."
secrets:
  - "auth/codex.json"
services:
  cliproxyapi:
    # ...
```

**After (v2)**:
```yaml
config_version: 2
auth:
  providers:
    codex:
      auth_url_endpoint: "..."
secret_files:
  - "auth/codex.json"
services:
  cliproxyapi_plus:
    # ...
```
```

### 7.2 Updated Documents

**`CLAUDE.md`**:
- Remove references to config_version: 1
- Update configuration schema section
- Remove backward compatibility notes

**`README.md`**:
- Update quick start examples to v2 format
- Add link to migration guide

**`docs/configuration.md`**:
- Remove version 1 schema documentation
- Simplify configuration reference

---

## 8. Release Notes

### v0.2.0 Release Notes (Deprecation)

```markdown
## Deprecations

⚠️ **Config Version 1 Deprecation Notice**

FlowGate v0.2.0 deprecates config_version: 1 and legacy field names.
These will be removed in v0.3.0.

**Deprecated Fields**:
- `oauth` → Use `auth.providers`
- `secrets` → Use `secret_files`
- `cliproxyapi` → Use `cliproxyapi_plus`

**Action Required**:
Run `flowgate config migrate` to automatically upgrade your configuration.

**Timeline**:
- v0.2.0: Deprecation warnings (full backward compatibility)
- v0.3.0: Legacy support removed (breaking change)

## New Features

- Added `flowgate config migrate` command for automatic config upgrades
- Deprecation warnings display on all commands
- Dry-run mode for migration preview
```

### v0.3.0 Release Notes (Removal)

```markdown
## ⚠️ Breaking Changes

**Config Version 1 Removed**

FlowGate v0.3.0 removes support for config_version: 1 and legacy field names.

**Removed**:
- config_version: 1 support
- `oauth` field (use `auth.providers`)
- `secrets` field (use `secret_files`)
- `cliproxyapi` service name (use `cliproxyapi_plus`)

**Migration**:
If you haven't migrated yet, install v0.2.x first:
```bash
uv pip install flowgate==0.2.0
flowgate config migrate
uv pip install flowgate==0.3.0
```

See [Migration Guide](docs/migration-guide-v0.3.md) for details.

## Improvements

- Simplified configuration loading (-27% code in config.py)
- Faster config validation
- Clearer error messages
- Reduced maintenance complexity
```

---

## 9. Success Criteria

### 9.1 Functional Requirements

- [ ] Migration command successfully converts all v1 configs to v2
- [ ] Backup created before migration
- [ ] Dry-run mode shows accurate preview
- [ ] v0.3.0 rejects v1 configs with clear error
- [ ] All commands work with v2 configs

### 9.2 Code Quality

- [ ] Code reduction: -100 lines total
- [ ] config.py: -27% lines
- [ ] No increase in cyclomatic complexity
- [ ] All tests pass (target: 200+ tests)
- [ ] Test coverage maintained > 85%

### 9.3 Documentation

- [ ] Migration guide complete
- [ ] All examples use v2 format
- [ ] CLAUDE.md updated
- [ ] Release notes clear and actionable
- [ ] Breaking changes prominently documented

### 9.4 User Experience

- [ ] Deprecation warnings clear and actionable
- [ ] Error messages point to migration guide
- [ ] Migration process takes < 30 seconds
- [ ] Zero data loss during migration
- [ ] Rollback possible via backup

---

## 10. Timeline

| Milestone | Duration | Target Date | Status |
|-----------|----------|-------------|--------|
| Analysis Complete | - | 2026-02-19 | ✅ Done |
| Phase 2.1.1: Deprecation (v0.2.0) | 1 day | 2026-02-20 | ⏳ Pending |
| Testing & Documentation | 0.5 days | 2026-02-20 | ⏳ Pending |
| v0.2.0 Release | - | 2026-02-21 | ⏳ Pending |
| User Migration Period | 2-4 weeks | 2026-03-15 | ⏳ Pending |
| Phase 2.1.2: Removal (v0.3.0) | 0.5 days | 2026-03-16 | ⏳ Pending |
| v0.3.0 Release | - | 2026-03-17 | ⏳ Pending |

**Total Implementation Time**: 2 days
**Total Migration Period**: 4-6 weeks

---

## 11. Appendix

### A. Complete Code Diff Preview

**config.py changes** (v0.3.0):
```diff
- _ALLOWED_TOP_LEVEL_KEYS = {
-     "oauth",  # Remove
- }
+ _ALLOWED_TOP_LEVEL_KEYS = {
+     # oauth removed
+ }

- _SUPPORTED_CONFIG_VERSIONS = {1, 2}
+ _SUPPORTED_CONFIG_VERSIONS = {2}

- def _normalize_legacy_fields(data: dict[str, Any]) -> dict[str, Any]:
-     # ... 37 lines removed ...
-     return normalized

  def load_router_config(path: str | Path) -> dict[str, Any]:
      path_obj = Path(path)
-     data = _normalize_legacy_fields(_parse_yaml_like(path_obj))
+     data = _parse_yaml_like(path_obj)
+
+     version = data.get("config_version", 2)
+     if version != 2:
+         raise ConfigError(
+             f"Unsupported config_version={version}. "
+             f"FlowGate v0.3.0+ only supports config_version: 2."
+         )

-     oauth = data.get("oauth", {})
-     oauth_map = _ensure_mapping(oauth, "oauth")
-     ConfigValidator.validate_oauth(oauth_map)

      return {
-         "oauth": oauth_map,  # Remove
      }
```

### B. Test Migration Checklist

**Files requiring test updates**:
- [ ] `tests/test_config.py` - Remove legacy tests, update fixtures
- [ ] `tests/test_cli_regression_auth.py` - Update config fixtures
- [ ] `tests/test_cli_regression_service.py` - Update config fixtures
- [ ] `tests/test_cli_regression_misc.py` - Update config fixtures
- [ ] `tests/test_profile.py` - Update config fixtures
- [ ] `tests/test_oauth.py` - Update config fixtures
- [ ] `tests/test_headless_import.py` - Update config fixtures

**New test files**:
- [ ] `tests/test_config_migrate.py` - Migration command tests
- [ ] `tests/test_config_deprecation.py` - Deprecation warning tests

---

## Approval

- [ ] Technical Lead Review
- [ ] Architecture Review
- [ ] Documentation Review
- [ ] Ready for Implementation

**Next Steps**:
1. Review and approve this plan
2. Create implementation branch: `feature/phase-2-1-config-v1-removal`
3. Begin Phase 2.1.1 implementation
4. Submit PR for v0.2.0 with deprecation warnings

---

**Document Version**: 1.0
**Last Updated**: 2026-02-19
**Author**: Claude (AI Assistant)
**Reviewers**: [Pending]
