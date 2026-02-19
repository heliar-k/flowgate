# Config Migrate Command Implementation

**Date**: 2026-02-19
**Status**: ✅ Complete
**Tests**: 203/203 passing (12 new tests added)

## Overview

Implemented `flowgate config migrate` command to automatically convert configuration files from version 1 to version 2, supporting the deprecation strategy outlined in Phase 2.1 of the migration plan.

## Implementation

### Files Created

1. **`src/flowgate/cli/commands/config.py`** (210 lines)
   - `ConfigMigrateCommand` class extending `BaseCommand`
   - Automatic detection of migration needs
   - Backup creation with timestamp
   - Dry-run mode support
   - YAML and JSON format support

2. **`tests/test_config_migrate.py`** (465 lines)
   - 12 comprehensive test cases
   - Tests for all migration scenarios
   - Edge case coverage (already v2, both oauth and auth, etc.)

### Files Modified

1. **`src/flowgate/cli/parser.py`**
   - Added `config` subcommand with `migrate` action
   - Added `--to-version` and `--dry-run` flags

2. **`src/flowgate/cli.py`**
   - Imported `ConfigMigrateCommand`
   - Added config command routing logic

## Features

### Command Usage

```bash
# Preview changes without writing
flowgate config migrate --dry-run

# Perform migration (default to version 2)
flowgate config migrate

# Specify target version explicitly
flowgate config migrate --to-version 2
```

### Migration Transformations

The command automatically performs these transformations:

1. **Version Update**: `config_version: 1` → `config_version: 2`
2. **OAuth Migration**: `oauth` → `auth.providers`
3. **Secrets Migration**: `secrets` → `secret_files`
4. **Service Name**: `services.cliproxyapi` → `services.cliproxyapi_plus`

### Safety Features

- **Automatic Backup**: Creates `.backup-TIMESTAMP` file before migration
- **Validation**: Validates migrated config before finalizing
- **Rollback**: Restores backup if validation fails
- **Dry-run Mode**: Preview changes without modifying files
- **Idempotent**: Running on v2 config is a no-op

## Example Output

### Dry-run Mode

```
📋 Analyzing configuration...
   Current version: 1
   Target version: 2

🔄 Migration changes:
   - Set 'config_version: 2'
   - Rename 'secrets' → 'secret_files'
   - Rename 'services.cliproxyapi' → 'services.cliproxyapi_plus'
   - Rename 'oauth' → 'auth.providers'

🔍 Dry-run mode: No changes will be written
```

### Actual Migration

```
📋 Analyzing configuration...
   Current version: 1
   Target version: 2

🔄 Migration changes:
   - Set 'config_version: 2'
   - Rename 'secrets' → 'secret_files'
   - Rename 'services.cliproxyapi' → 'services.cliproxyapi_plus'
   - Rename 'oauth' → 'auth.providers'

💾 Creating backup: config/flowgate.yaml.backup-20260219-143022
✅ Configuration migrated successfully!
   New config: config/flowgate.yaml
   Backup: config/flowgate.yaml.backup-20260219-143022
```

### Already Version 2

```
📋 Analyzing configuration...
   Current version: 2
   Target version: 2

✅ Configuration is already at version 2
   No migration needed
```

## Test Coverage

### Test Cases (12 total)

1. ✅ `test_migrate_v1_to_v2_json` - JSON format migration
2. ✅ `test_migrate_v1_to_v2_yaml` - YAML format migration
3. ✅ `test_migrate_already_v2_no_op` - No-op for v2 configs
4. ✅ `test_migrate_dry_run_no_changes` - Dry-run doesn't modify files
5. ✅ `test_migrate_creates_backup` - Backup creation verification
6. ✅ `test_migrate_oauth_to_auth_providers` - OAuth field migration
7. ✅ `test_migrate_secrets_to_secret_files` - Secrets field migration
8. ✅ `test_migrate_cliproxyapi_to_cliproxyapi_plus` - Service name migration
9. ✅ `test_migrate_shows_all_changes` - Output completeness
10. ✅ `test_migrate_with_both_oauth_and_auth` - Edge case handling
11. ✅ `test_migrate_invalid_target_version` - Error handling
12. ✅ `test_migrate_missing_config_file` - Missing file handling

### Test Results

```
Ran 203 tests in 1.360s
OK
```

- Original tests: 191
- New tests: 12
- Total: 203
- Pass rate: 100%

## Code Quality

### Implementation Highlights

- **Error Handling**: Comprehensive exception handling with clear error messages
- **Type Safety**: Full type hints on all public methods
- **Documentation**: Docstrings for all classes and methods
- **User Feedback**: Clear, emoji-enhanced progress messages
- **Validation**: Pre and post-migration validation
- **Format Preservation**: Maintains YAML/JSON format of original file

### Design Patterns

- Follows existing `BaseCommand` pattern
- Uses `@handle_command_errors` decorator for consistent error handling
- Integrates with existing CLI routing infrastructure
- Maintains separation of concerns (parsing, migration, validation)

## Integration

### CLI Integration

The command is fully integrated into the FlowGate CLI:

```bash
$ flowgate --help
positional arguments:
  {profile,status,health,doctor,integration,auth,service,bootstrap,config}

$ flowgate config --help
positional arguments:
  {migrate}

$ flowgate config migrate --help
options:
  --to-version TO_VERSION
  --dry-run
```

### Deprecation Warning Integration

Works seamlessly with existing deprecation warnings:

```
⚠️  WARNING: config_version 1 is deprecated and will be removed in v0.3.0
Please migrate your configuration to version 2.
Run: flowgate config migrate --to-version 2
```

## Next Steps

### Phase 2.1.2: Remove Legacy Support (v0.3.0)

With the migration command in place, the next phase can proceed:

1. Remove `_normalize_legacy_fields()` function
2. Remove `oauth` from `_ALLOWED_TOP_LEVEL_KEYS`
3. Change `_SUPPORTED_CONFIG_VERSIONS = {2}`
4. Remove `validate_oauth()` from validators
5. Simplify `_auth_providers()` helper
6. Update all test configs to v2 format

## Acceptance Criteria

All acceptance criteria from the migration plan have been met:

- ✅ Deprecation warnings display for all legacy fields
- ✅ Migration command successfully converts v1 → v2
- ✅ Backup created before migration
- ✅ Dry-run mode works correctly
- ✅ All tests pass (203/203)
- ✅ Clear user feedback with emoji indicators
- ✅ Command integrated into main CLI
- ✅ Comprehensive test coverage

## Conclusion

The `flowgate config migrate` command is production-ready and provides a smooth migration path for users upgrading from config version 1 to version 2. The implementation is robust, well-tested, and follows all FlowGate coding standards.
