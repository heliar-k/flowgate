# Config Version Migration Guide

## Overview
FlowGate configuration schema version 1 is deprecated as of v0.2.0 and will be removed in v0.3.0.

## Deprecation Timeline

| Version | Status | Action |
|---------|--------|--------|
| v0.2.0 | Deprecation warning + migrate command | Version 1 still works, warning displayed, migration tool available |
| v0.3.0 | Version 1 removed | Version 1 configs will no longer load |

## What Changed

### Field Renames (v1 → v2)

| Version 1 Field | Version 2 Field | Notes |
|----------------|-----------------|-------|
| `oauth` | `auth.providers` | OAuth config moved under auth section |
| `secrets` | `secret_files` | Clearer naming for secret file paths |
| `services.cliproxyapi` | `services.cliproxyapi_plus` | Service name updated |

### Config Version Declaration

**Version 1 (implicit or explicit):**
```yaml
# No config_version specified (defaults to 1 in old configs)
# OR
config_version: 1
```

**Version 2 (recommended):**
```yaml
config_version: 2
```

## Migration Steps

### Manual Migration

1. Add `config_version: 2` to your config file
2. Rename fields according to the table above:
   - `oauth` → `auth.providers`
   - `secrets` → `secret_files`
   - `services.cliproxyapi` → `services.cliproxyapi_plus`

### Example Migration

**Before (Version 1):**
```yaml
config_version: 1
oauth:
  codex:
    auth_url_endpoint: "http://127.0.0.1:9000/auth-url"
    status_endpoint: "http://127.0.0.1:9000/status"
secrets:
  - "auth/codex.json"
services:
  cliproxyapi:
    host: "127.0.0.1"
    port: 9000
```

**After (Version 2):**
```yaml
config_version: 2
auth:
  providers:
    codex:
      auth_url_endpoint: "http://127.0.0.1:9000/auth-url"
      status_endpoint: "http://127.0.0.1:9000/status"
secret_files:
  - "auth/codex.json"
services:
  cliproxyapi_plus:
    host: "127.0.0.1"
    port: 9000
```

## Automated Migration

The `flowgate config migrate` command is available in v0.2.0 and later.

```bash
# Preview migration without applying changes
flowgate --config config/flowgate.yaml config migrate --dry-run

# Perform migration (creates automatic backup)
flowgate --config config/flowgate.yaml config migrate

# Specify target version explicitly (default is 2)
flowgate --config config/flowgate.yaml config migrate --to-version 2
```

The migration command will:
1. Analyze your current configuration
2. Identify all legacy fields that need updating
3. Create a timestamped backup (e.g., `flowgate.yaml.backup-20260219-110218`)
4. Apply all necessary transformations
5. Validate the migrated configuration

### Migration Safety

- Automatic backup created before any changes
- Dry-run mode available to preview changes
- Idempotent: safe to run multiple times
- Validates config after migration
- Preserves all custom settings and values

## Checking Your Config Version

```bash
# Load config and check for warnings
flowgate --config config/flowgate.yaml status

# If you see this warning, you need to migrate:
⚠️  WARNING: config_version 1 is deprecated and will be removed in v0.3.0
```

## Backward Compatibility

Version 1 configs continue to work in v0.2.x releases:
- All legacy field names are automatically mapped to new names
- Functionality is unchanged
- Only a warning is displayed

## FAQ

**Q: Do I need to migrate immediately?**
A: Yes, it's strongly recommended. Version 1 will stop working in v0.3.0. Migrate now to avoid disruption.

**Q: Will my existing config break?**
A: No, version 1 configs continue to work in v0.2.x with a deprecation warning.

**Q: Can I use both old and new field names?**
A: New field names take precedence. The migration command will remove duplicate legacy fields. It's best to use only version 2 field names.

**Q: What if I don't specify config_version?**
A: New configs default to version 2. Existing configs without a version are treated as version 1 and will show deprecation warnings.

**Q: What if migration fails?**
A: The original config is preserved as a backup file. Simply restore from the backup and report the issue.

**Q: Can I rollback after migration?**
A: Yes, restore from the automatic backup file created during migration (e.g., `flowgate.yaml.backup-20260219-110218`).

## Support

If you encounter issues during migration:
1. Check the warning message for specific legacy fields detected
2. Refer to example configs in `config/examples/`
3. Run `flowgate doctor` to validate your configuration
4. See `docs/runbook-troubleshooting.md` for common issues
